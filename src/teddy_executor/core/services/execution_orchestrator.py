from datetime import datetime

from typing import Any, Optional, Sequence

from teddy_executor.core.domain.models import (
    ActionData,
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
        # Scenario: Universal PROMPT Auto-Execution
        # Single PROMPT actions bypass approval for fluid conversation.
        if len(plan.actions) == 1 and plan.actions[0].type == "PROMPT":
            return plan

        # We only call the bulk review (TUI) if interactive is True AND a reviewer is present.
        if interactive and self._plan_reviewer:
            return self._plan_reviewer.review(plan)
        return plan

    def _process_plan_actions(self, plan: Plan, interactive: bool) -> list[ActionLog]:
        """Iterates through actions and dispatches them."""
        action_logs = []
        halt_execution = False
        for action in plan.actions:
            action_log, should_halt = self._handle_action_in_loop(
                action, plan, interactive, halt_execution
            )
            action_logs.append(action_log)
            if should_halt:
                halt_execution = True
        return action_logs

    def _handle_action_in_loop(
        self, action: ActionData, plan: Plan, interactive: bool, halt_execution: bool
    ) -> tuple[ActionLog, bool]:
        """Logic for processing a single action within the execution loop."""
        if halt_execution:
            return (
                self._action_executor.handle_skipped_action(
                    action, "Skipped because a previous action failed."
                ),
                True,
            )

        if action.executed and action.action_log:
            should_halt = (
                action.action_log.status == ActionStatus.FAILURE
                and not action.params.get("allow_failure")
            )
            return action.action_log, should_halt

        if not action.selected:
            reason = "User deselected this action in the plan reviewer."
            if action.is_terminal:
                reason = (
                    "Automatically skipped: This action must be performed in isolation."
                )
            return (
                self._action_executor.handle_skipped_action(action, reason),
                False,
            )

        action_log, captured_message = self._dispatch_single_action(
            action, plan, interactive
        )
        if captured_message:
            plan.metadata["user_request"] = captured_message

        should_halt = (
            action_log.status == ActionStatus.FAILURE
            and not action.params.get("allow_failure")
        )
        return action_log, should_halt

    def _dispatch_single_action(
        self, action: Any, plan: Plan, interactive: bool
    ) -> tuple[ActionLog, str]:
        """Handles the review and dispatch of a single action."""
        agent_name = plan.metadata.get("Agent") or plan.metadata.get("agent")
        reviewer_handled = False
        should_dispatch = True
        captured_message = ""

        # Scenario: Universal PROMPT Auto-Execution
        # Single PROMPT actions bypass approval for fluid conversation.
        is_single_prompt = len(plan.actions) == 1 and action.type == "PROMPT"

        if interactive and self._plan_reviewer and not is_single_prompt:
            should_dispatch, captured_message = self._plan_reviewer.review_action(
                action, len(plan.actions), agent_name=agent_name
            )
            reviewer_handled = True

        if not should_dispatch:
            reason = "User skipped this action in the plan reviewer."
            if action.is_terminal:
                reason = (
                    "Automatically skipped: This action must be performed in isolation."
                )
            return (
                self._action_executor.handle_skipped_action(action, reason),
                "",
            )

        if reviewer_handled:
            # Reviewer (TUI) handled approval, execute immediately skipping isolation.
            action_log, dispatch_message = self._action_executor.confirm_and_dispatch(
                action,
                interactive=False,
                total_actions=len(plan.actions),
                agent_name=agent_name,
                is_session=plan.is_session,
                skip_isolation=True,
            )
            return action_log, dispatch_message or captured_message

        # Fallback to ActionExecutor interaction if no reviewer is present.
        return self._action_executor.confirm_and_dispatch(
            action,
            interactive=interactive,
            total_actions=len(plan.actions),
            agent_name=agent_name,
            is_session=plan.is_session,
        )

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> ExecutionReport:
        import os
        import tempfile

        temp_plan_path = None
        try:
            if plan is None:
                if plan_content is not None:
                    # Scenario: TUI "View Plan" Workflow
                    # If content is provided without a path, persist it to a temporary file
                    # so the TUI has a physical file to open for previewing.
                    if not plan_path:
                        # We use a known prefix to help identify it as a TeDDy manual plan
                        temp_fd, temp_plan_path = tempfile.mkstemp(
                            prefix="teddy_manual_plan_", suffix=".md"
                        )
                        os.close(temp_fd)
                        self._file_system_manager.write_file(
                            temp_plan_path, plan_content
                        )
                        plan_path = temp_plan_path

                    plan = self._plan_parser.parse(plan_content, plan_path=plan_path)
                elif plan_path is not None:
                    content = self._file_system_manager.read_file(plan_path)
                    plan = self._plan_parser.parse(content, plan_path=plan_path)
                else:
                    raise ValueError(
                        "Must provide either plan, plan_content, or plan_path"
                    )

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
        finally:
            if temp_plan_path and os.path.exists(temp_plan_path):
                try:
                    os.remove(temp_plan_path)
                except Exception:  # nosec B110
                    # Silently fail on cleanup errors (e.g. file busy)
                    pass

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
