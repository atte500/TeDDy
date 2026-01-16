from datetime import datetime

from teddy_executor.core.domain.models import (
    ActionLog,
    ExecutionReport,
    Plan,
    RunSummary,
    RunStatus,
    ActionStatus,
)
from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.plan_parser import PlanParser


class ExecutionOrchestrator:
    def __init__(
        self,
        plan_parser: PlanParser,
        action_dispatcher: ActionDispatcher,
        user_interactor: IUserInteractor,
    ):
        self._plan_parser = plan_parser
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor

    def execute(self, plan_content: str, interactive: bool) -> ExecutionReport:
        start_time = datetime.now()
        action_logs = []
        overall_status: RunStatus = RunStatus.SUCCESS

        plan: Plan = self._plan_parser.parse(plan_content)

        for action in plan.actions:
            should_dispatch = True
            reason = ""
            if interactive:
                prompt = f"Execute action: {action.type} with params {action.params}?"
                should_dispatch, reason = self._user_interactor.confirm_action(prompt)

            if should_dispatch:
                action_log = self._action_dispatcher.dispatch_and_execute(action)
            else:
                action_log = ActionLog(
                    status=ActionStatus.SKIPPED,
                    action_type=action.type,
                    params=action.params,
                    details=f"User skipped this action. Reason: {reason}",
                )

            action_logs.append(action_log)
            if action_log.status in [ActionStatus.FAILURE, ActionStatus.SKIPPED]:
                overall_status = RunStatus.FAILURE

        end_time = datetime.now()
        summary = RunSummary(
            status=overall_status,
            start_time=start_time,
            end_time=end_time,
        )

        return ExecutionReport(
            run_summary=summary,
            action_logs=action_logs,
        )
