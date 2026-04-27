import logging
from datetime import datetime

from typing import Any, Optional

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ExecutionReport,
    Plan,
    ActionStatus,
)
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.ports.outbound.execution_report_assembler import (
    IExecutionReportAssembler,
)
from teddy_executor.core.services.action_executor import ActionExecutor

logger = logging.getLogger(__name__)


class ExecutionOrchestrator(IRunPlanUseCase):
    def __init__(  # noqa: PLR0913
        self,
        plan_parser: IPlanParser,
        plan_validator: IPlanValidator,
        action_executor: ActionExecutor,
        file_system_manager: IFileSystemManager,
        report_assembler: IExecutionReportAssembler,
        plan_reviewer: IPlanReviewer = None,  # type: ignore
    ):
        self._plan_parser = plan_parser
        self._plan_validator = plan_validator
        self._action_executor = action_executor
        self._file_system_manager = file_system_manager
        self._report_assembler = report_assembler
        self._plan_reviewer = plan_reviewer

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

        return self._report_assembler.assemble(plan, action_logs, start_time, message)

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
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

            reviewed_plan = self._perform_interactive_review(plan, interactive)
            if reviewed_plan is None:
                return self._handle_aborted_execution(plan, start_time, message)

            action_logs = self._process_plan_actions(reviewed_plan, interactive)
            return self._report_assembler.assemble(
                reviewed_plan, action_logs, start_time, message
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
        _session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """Stateless orchestrator does not support session resumption."""
        raise NotImplementedError(
            "Session operations are not supported in stateless ExecutionOrchestrator."
        )
