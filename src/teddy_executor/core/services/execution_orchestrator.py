from datetime import datetime

from typing import Optional, Sequence

from teddy_executor.core.domain.models import (
    ActionLog,
    ExecutionReport,
    Plan,
    RunSummary,
    RunStatus,
    ActionStatus,
)
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.action_executor import ActionExecutor


class ExecutionOrchestrator(IRunPlanUseCase):
    def __init__(
        self,
        plan_parser: IPlanParser,
        plan_validator: IPlanValidator,
        action_executor: ActionExecutor,
        file_system_manager: IFileSystemManager,
        plan_reviewer: IPlanReviewer = None,  # type: ignore
    ):
        self._plan_parser = plan_parser
        self._plan_validator = plan_validator
        self._action_executor = action_executor
        self._file_system_manager = file_system_manager
        self._plan_reviewer = plan_reviewer

    def _determine_overall_status(self, action_logs: Sequence[ActionLog]) -> RunStatus:
        """Determines the final run status based on the hierarchy of action outcomes."""
        if not action_logs:
            return RunStatus.SUCCESS

        statuses = [log.status for log in action_logs]
        if ActionStatus.FAILURE in statuses:
            return RunStatus.FAILURE

        # Success takes precedence: if any action succeeded, the run is a success.
        if ActionStatus.SUCCESS in statuses:
            return RunStatus.SUCCESS

        # If every single action was skipped, the run is skipped.
        if statuses and all(s == ActionStatus.SKIPPED for s in statuses):
            return RunStatus.SKIPPED

        return RunStatus.SUCCESS

    def _perform_interactive_review(self, plan: Plan, interactive: bool) -> Plan | None:
        """Allows the user to review and modify the plan before execution."""
        # We only call the bulk review (TUI) if interactive is True AND a reviewer is present.
        if interactive and self._plan_reviewer:
            return self._plan_reviewer.review(plan)
        return plan

    def _process_plan_actions(self, plan: Plan, interactive: bool) -> list[ActionLog]:
        """Iterates through actions and dispatches them."""
        action_logs = []
        halt_execution = False
        for action in plan.actions:
            if halt_execution:
                reason = "Skipped because a previous action failed."
                action_logs.append(
                    self._action_executor.handle_skipped_action(action, reason)
                )
                continue

            if not action.selected:
                reason = "User deselected this action in the plan reviewer."
                action_logs.append(
                    self._action_executor.handle_skipped_action(action, reason)
                )
                continue

            agent_name = plan.metadata.get("Agent") or plan.metadata.get("agent")

            reviewer_handled = False
            should_dispatch = True
            captured_message = ""
            if interactive and self._plan_reviewer:
                should_dispatch, captured_message = self._plan_reviewer.review_action(
                    action, len(plan.actions), agent_name=agent_name
                )
                reviewer_handled = True

            if not should_dispatch:
                action_log = self._action_executor.handle_skipped_action(
                    action, "User skipped this action in the plan reviewer."
                )
            elif reviewer_handled:
                # Reviewer already confirmed it, so execute immediately.
                # We skip isolation because the reviewer (TUI) allows multi-action execution.
                action_log, dispatch_message = (
                    self._action_executor.confirm_and_dispatch(
                        action,
                        interactive=False,
                        total_actions=len(plan.actions),
                        agent_name=agent_name,
                        is_session=plan.is_session,
                        skip_isolation=True,
                    )
                )
                # If the executor (e.g. via a modal editor in TUI) returned a message, it takes precedence
                if dispatch_message:
                    captured_message = dispatch_message
            else:
                # Fallback to ActionExecutor interaction ONLY if no reviewer is present
                action_log, captured_message = (
                    self._action_executor.confirm_and_dispatch(
                        action,
                        interactive=interactive,
                        total_actions=len(plan.actions),
                        agent_name=agent_name,
                        is_session=plan.is_session,
                    )
                )

            if captured_message:
                plan.metadata["user_request"] = captured_message

            action_logs.append(action_log)

            if action_log.status == ActionStatus.FAILURE:
                allow_failure = action.params.get("allow_failure")
                if not allow_failure:
                    halt_execution = True
        return action_logs

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> ExecutionReport:
        if plan is None:
            if plan_content is not None:
                plan = self._plan_parser.parse(plan_content, plan_path=plan_path)
            elif plan_path is not None:
                content = self._file_system_manager.read_file(plan_path)
                plan = self._plan_parser.parse(content, plan_path=plan_path)
            else:
                raise ValueError("Must provide either plan, plan_content, or plan_path")

        start_time = datetime.now()

        # Pre-flight logical validation
        validation_errors = self._plan_validator.validate(plan)
        if validation_errors:
            error_msgs = "\n---\n".join(e.message for e in validation_errors)
            raise InvalidPlanError(
                f"Plan failed logical validation:\n{error_msgs}",
                offending_nodes=[
                    e.offending_node for e in validation_errors if e.offending_node
                ],
                validation_errors=validation_errors,
            )

        plan = self._perform_interactive_review(plan, interactive)
        if plan is None:
            return ExecutionReport(
                run_summary=RunSummary(
                    status=RunStatus.SKIPPED,
                    start_time=start_time,
                    end_time=datetime.now(),
                ),
                plan_title="",
                rationale="",
                metadata={},
                original_actions=[],
                action_logs=[],
            )

        action_logs = self._process_plan_actions(plan, interactive)

        summary = RunSummary(
            status=self._determine_overall_status(action_logs),
            start_time=start_time,
            end_time=datetime.now(),
        )

        # Capture any message added during the execution loop or passed from CLI
        final_user_request = plan.metadata.get("user_request") or message

        return ExecutionReport(
            run_summary=summary,
            plan_title=plan.title,
            rationale=plan.rationale,
            user_request=final_user_request,
            metadata=plan.metadata,
            original_actions=plan.actions,
            action_logs=action_logs,
        )

    def resume(
        self,
        _session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """Stateless orchestrator does not support session resumption."""
        raise NotImplementedError(
            "Session operations are not supported in stateless ExecutionOrchestrator."
        )
