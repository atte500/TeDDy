import logging
from datetime import datetime

from typing import Any, Optional

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ExecutionReport,
    Plan,
    ReportAssemblyData,
    ActionStatus,
)
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts

logger = logging.getLogger(__name__)


class ExecutionOrchestrator(IRunPlanUseCase):
    def __init__(
        self,
        ports: OrchestratorPorts,
    ):
        self._plan_parser = ports.plan_parser
        self._plan_validator = ports.plan_validator
        self._action_executor = ports.action_executor
        self._file_system_manager = ports.file_system_manager
        self._report_assembler = ports.report_assembler
        self._user_interactor = ports.user_interactor
        self._plan_reviewer = ports.plan_reviewer

    def _perform_interactive_review(
        self,
        plan: Plan,
        interactive: bool,
        project_context: Optional[Any] = None,
    ) -> Plan | None:
        """Allows the user to review and modify the plan before execution."""
        # Scenario: Communication Turns (MESSAGE) bypass TUI
        # Single-action communication turns bypass approval for fluid conversation.
        if plan.is_communication_turn():
            return plan

        # We only call the bulk review (TUI) if interactive is True AND a reviewer is present.
        if interactive and self._plan_reviewer:
            reviewed_plan = self._plan_reviewer.review(
                plan, project_context=project_context
            )
            # Harden against Mocks in tests: if it's not a Plan or None, use the original plan
            if reviewed_plan is not None and not isinstance(reviewed_plan, Plan):
                return plan
            return reviewed_plan
        return plan

    def _process_plan_actions(
        self, plan: Plan, interactive: bool, project_context: Optional[Any] = None
    ) -> list[ActionLog]:
        """Iterates through actions and dispatches them."""
        action_logs = []
        halt_execution = False
        for action in plan.actions:
            action_log, should_halt = self._handle_action_in_loop(
                action,
                plan,
                interactive,
                halt_execution,
                project_context=project_context,
            )
            action_logs.append(action_log)
            if should_halt:
                halt_execution = True
        return action_logs

    def _handle_action_in_loop(
        self,
        action: ActionData,
        plan: Plan,
        interactive: bool,
        halt_execution: bool,
        project_context: Optional[Any] = None,
    ) -> tuple[ActionLog, bool]:
        """Logic for processing a single action within the execution loop."""
        if halt_execution:
            return (
                self._action_executor.handle_skipped_action(
                    action,
                    "Skipped because a previous action failed. (Hint: use 'Allow Failure: true' in EXECUTE actions to proceed even with non-zero exit codes.)",
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
            return (
                self._action_executor.handle_skipped_action(action, reason),
                False,
            )

        # READ skip: if file is already in context (turn or session), skip the read
        if (
            plan.is_session
            and action.type.upper() == "READ"
            and project_context
            and hasattr(project_context, "items")
            and project_context.items
        ):
            target_path = (
                action.params.get("File Path")
                or action.params.get("path")
                or action.params.get("Resource")
                or ""
            )
            if target_path and any(
                item.path == target_path for item in project_context.items
            ):
                return (
                    self._action_executor.handle_skipped_action(
                        action,
                        "Latest content is already in session context.",
                    ),
                    False,
                )

        try:
            action_log, captured_message = self._dispatch_single_action(
                action, plan, interactive
            )
        except Exception as e:
            action_log = self._action_executor.handle_failed_action(action, str(e))
            captured_message = ""

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

        # Scenario: Communication Turns (MESSAGE) bypass confirmation
        # Single communication actions bypass approval for fluid conversation.
        is_communication_action = plan.is_communication_turn()

        if interactive and self._plan_reviewer and not is_communication_action:
            should_dispatch, captured_message = self._plan_reviewer.review_action(
                action, len(plan.actions), agent_name=agent_name
            )
            reviewer_handled = True

        if not should_dispatch:
            reason = "User skipped this action in the plan reviewer."
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

    def _resolve_plan(
        self,
        plan: Optional[Plan],
        plan_content: Optional[str],
        plan_path: Optional[str],
    ) -> tuple[Plan, Optional[str]]:
        """Resolves the plan from content, path, or object, creating a temp file if needed."""
        import tempfile

        if plan:
            return plan, None

        temp_path = None
        if plan_content is not None:
            if not plan_path:
                import os

                fd, temp_path = tempfile.mkstemp(
                    prefix="teddy_manual_plan_", suffix=".md"
                )
                os.close(fd)
                self._file_system_manager.write_file(temp_path, plan_content)
                plan_path = temp_path
            return (
                self._plan_parser.parse(plan_content, plan_path=plan_path),
                temp_path,
            )

        if plan_path is not None:
            content = self._file_system_manager.read_file(plan_path)
            return self._plan_parser.parse(content, plan_path=plan_path), None

        raise ValueError("Must provide either plan, plan_content, or plan_path")

    def _handle_aborted_execution(
        self, plan: Plan, start_time: datetime, message: Optional[str]
    ) -> ExecutionReport:
        """Generates a report for an execution aborted by the user."""
        from dataclasses import replace
        from teddy_executor.core.domain.models import RunStatus

        # If a message was captured in the TUI (via 'm' key), propagate it.
        resolved_message = message or plan.metadata.get("user_request")

        action_logs = []
        for a in plan.actions:
            if a.executed and a.action_log:
                action_logs.append(a.action_log)
            else:
                action_logs.append(
                    self._action_executor.handle_skipped_action(
                        a, "Execution aborted by user."
                    )
                )

        report = self._report_assembler.assemble(
            ReportAssemblyData(
                plan=plan,
                action_logs=action_logs,
                start_time=start_time,
                message=resolved_message,
            )
        )
        return replace(
            report, run_summary=replace(report.run_summary, status=RunStatus.ABORTED)
        )

    def execute(  # noqa: PLR0913
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
        project_context: Optional[Any] = None,
    ) -> ExecutionReport:
        import os

        temp_plan_path = None
        try:
            plan, temp_plan_path = self._resolve_plan(plan, plan_content, plan_path)
            start_time = datetime.now()

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

            reviewed_plan = self._perform_interactive_review(
                plan, interactive, project_context=project_context
            )
            if reviewed_plan is None:
                return self._handle_aborted_execution(plan, start_time, message)

            action_logs = self._process_plan_actions(
                reviewed_plan, interactive, project_context=project_context
            )
            return self._report_assembler.assemble(
                ReportAssemblyData(
                    plan=reviewed_plan,
                    action_logs=action_logs,
                    start_time=start_time,
                    message=message,
                    is_session=reviewed_plan.is_session,
                )
            )
        finally:
            if temp_plan_path and os.path.exists(temp_plan_path):
                try:
                    os.remove(temp_plan_path)
                except Exception as e:
                    logger.debug(
                        "Failed to clean up temporary plan file %s: %s",
                        temp_plan_path,
                        e,
                    )

    def resume(
        self,
        session_name: str,
        interactive: bool = True,
        project_context: Optional[Any] = None,
    ) -> Optional[ExecutionReport]:
        """Stateless orchestrator does not support session resumption."""
        raise NotImplementedError(
            "Session operations are not supported in stateless ExecutionOrchestrator."
        )
