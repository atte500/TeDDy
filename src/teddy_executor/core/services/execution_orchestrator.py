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
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor
from teddy_executor.core.services.action_executor import ActionExecutor


class ExecutionOrchestrator(IRunPlanUseCase):
    def __init__(
        self,
        plan_parser: IPlanParser,
        action_executor: ActionExecutor,
        user_interactor: IUserInteractor,
        file_system_manager: IFileSystemManager,
        plan_reviewer: IPlanReviewer = None,  # type: ignore
    ):
        self._plan_parser = plan_parser
        self._action_executor = action_executor
        self._user_interactor = user_interactor
        self._file_system_manager = file_system_manager
        self._plan_reviewer = plan_reviewer

    def _determine_overall_status(self, action_logs: Sequence[ActionLog]) -> RunStatus:
        """Determines the final run status based on the hierarchy of action outcomes."""
        if not action_logs:
            return RunStatus.SUCCESS

        statuses = {log.status for log in action_logs}
        if ActionStatus.FAILURE in statuses:
            return RunStatus.FAILURE
        if ActionStatus.SUCCESS in statuses:
            return RunStatus.SUCCESS
        # If no failures and no successes, it means everything was skipped.
        if all(s == ActionStatus.SKIPPED for s in statuses):
            return RunStatus.SKIPPED
        return RunStatus.SUCCESS

    def _perform_interactive_review(self, plan: Plan) -> Plan | None:
        """Allows the user to review and modify the plan before execution."""
        if not self._plan_reviewer:
            return plan
        return self._plan_reviewer.review(plan)

    def _process_plan_actions(self, plan: Plan, interactive: bool) -> list[ActionLog]:
        """Iterates through actions and dispatches them."""
        action_logs = []
        halt_execution = False
        for action in plan.actions:
            if halt_execution:
                reason = "Skipped because a previous action failed."
                self._user_interactor.notify_skipped_action(action, reason)
                action_logs.append(
                    self._action_executor.handle_skipped_action(action, reason)
                )
                continue

            if not action.selected:
                reason = "User deselected this action in the plan reviewer."
                self._user_interactor.notify_skipped_action(action, reason)
                action_logs.append(
                    self._action_executor.handle_skipped_action(action, reason)
                )
                continue

            action_log = self._action_executor.confirm_and_dispatch(
                action, interactive, len(plan.actions)
            )
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
    ) -> ExecutionReport:
        if plan is None:
            if plan_content is not None:
                plan = self._plan_parser.parse(plan_content)
            elif plan_path is not None:
                content = self._file_system_manager.read_file(plan_path)
                plan = self._plan_parser.parse(content)
            else:
                raise ValueError("Must provide either plan, plan_content, or plan_path")

        start_time = datetime.now()
        plan = self._perform_interactive_review(plan)
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

        return ExecutionReport(
            run_summary=summary,
            plan_title=plan.title,
            rationale=plan.rationale,
            metadata=plan.metadata,
            original_actions=plan.actions,
            action_logs=action_logs,
        )

    def resume(
        self, session_name: str, interactive: bool = True
    ) -> Optional[ExecutionReport]:
        """Stateless orchestrator does not support session resumption."""
        raise NotImplementedError(
            "Session operations are not supported in stateless ExecutionOrchestrator."
        )
