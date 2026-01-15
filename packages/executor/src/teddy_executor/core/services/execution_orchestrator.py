from datetime import datetime
from pathlib import Path
from typing import Literal

from teddy_executor.core.domain.models import (
    V2_ActionLog,
    V2_ExecutionReport,
    V2_RunSummary,
    V2_TeddyProject,
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

    def execute(self, plan_path: Path, interactive: bool) -> V2_ExecutionReport:
        """
        Coordinates the end-to-end execution of a plan.

        Args:
            plan_path: The path to the plan file.
            interactive: A flag to enable/disable step-by-step user approval.

        Returns:
            An ExecutionReport summarizing the entire run.
        """
        start_time = datetime.now()
        action_logs = []
        Status = Literal["SUCCESS", "FAILURE", "SKIPPED"]
        overall_status: Status = "SUCCESS"

        plan = self._plan_parser.parse(plan_path)

        for action in plan.actions:
            should_dispatch = True
            reason = ""
            if interactive:
                # TODO: Create a richer prompt string representation of the action
                prompt = f"Execute action: {action.type} with params {action.params}?"
                should_dispatch, reason = self._user_interactor.confirm_action(prompt)

            if should_dispatch:
                action_log = self._action_dispatcher.dispatch_and_execute(action)
            else:
                action_log = V2_ActionLog(
                    status="SKIPPED",
                    action_type=action.type,
                    params=action.params,
                    details=f"User skipped this action. Reason: {reason}",
                )

            action_logs.append(action_log)
            if action_log.status == "FAILURE":
                overall_status = "FAILURE"

        end_time = datetime.now()
        summary = V2_RunSummary(
            status=overall_status,
            start_time=start_time,
            end_time=end_time,
            project=V2_TeddyProject(name="unknown"),
        )

        return V2_ExecutionReport(
            run_summary=summary,
            action_logs=action_logs,
        )
