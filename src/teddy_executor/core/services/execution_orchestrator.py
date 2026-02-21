from datetime import datetime

from typing import Sequence

from teddy_executor.core.domain.models import (
    ActionLog,
    ExecutionReport,
    Plan,
    RunSummary,
    RunStatus,
    ActionStatus,
)
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


class ExecutionOrchestrator(RunPlanUseCase):
    def __init__(
        self,
        plan_parser: IPlanParser,
        action_dispatcher: ActionDispatcher,
        user_interactor: IUserInteractor,
        file_system_manager: IFileSystemManager,
    ):
        self._plan_parser = plan_parser
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor
        self._file_system_manager = file_system_manager

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

    def execute(self, plan_content: str, interactive: bool) -> ExecutionReport:
        start_time = datetime.now()
        action_logs = []

        try:
            plan: Plan = self._plan_parser.parse(plan_content)
        except Exception as e:
            # Handle parsing/validation errors gracefully
            # We treat any exception during parsing as a validation failure
            # import here to avoid circular dependency if any

            error_message = str(e)
            # If it's a ValueError (e.g. empty plan), wrap it nicely
            if isinstance(e, ValueError) and "Plan must contain" in str(e):
                error_message = str(e)

            return ExecutionReport(
                run_summary=RunSummary(
                    status=RunStatus.VALIDATION_FAILED,
                    start_time=start_time,
                    end_time=datetime.now(),
                ),
                validation_result=[error_message],
                action_logs=[],
            )

        halt_execution = False

        for action in plan.actions:
            if halt_execution:
                log_params = action.params.copy()
                if action.description:
                    log_params["Description"] = action.description
                action_logs.append(
                    ActionLog(
                        status=ActionStatus.SKIPPED,
                        action_type=action.type,
                        params=log_params,
                        details="Skipped because a previous action failed.",
                    )
                )
                continue

            should_dispatch = True
            reason = ""
            if interactive and action.type.lower() != "chat_with_user":
                # Build a more descriptive, multi-line prompt for readability
                prompt_parts = [
                    "---",
                    f"Action: {action.type}",
                ]
                if action.description:
                    prompt_parts.append(f"Description: {action.description}")

                # Use a cleaner representation of params from the original action
                param_str = "\n".join(f"  - {k}: {v}" for k, v in action.params.items())
                prompt_parts.append("Parameters:")
                prompt_parts.append(param_str)
                prompt_parts.append("---\nApprove action?")

                prompt = "\n".join(prompt_parts)
                should_dispatch, reason = self._user_interactor.confirm_action(
                    action=action, action_prompt=prompt
                )

            if should_dispatch:
                action_log = self._action_dispatcher.dispatch_and_execute(action)

                # If CREATE or EDIT failed, try to capture file content for context
                if action_log.status == ActionStatus.FAILURE and action.type in (
                    "CREATE",
                    "EDIT",
                ):
                    path = action.params.get("path") or action.params.get("File Path")
                    if path:
                        try:
                            content = self._file_system_manager.read_file(path)
                            # Create a new ActionLog with updated details
                            new_details = (
                                action_log.details
                                if isinstance(action_log.details, dict)
                                else {"original_details": action_log.details}
                            )
                            new_details["content"] = content

                            action_log = ActionLog(
                                status=action_log.status,
                                action_type=action_log.action_type,
                                params=action_log.params,
                                details=new_details,
                            )
                        except Exception:
                            # If we can't read the file (e.g. doesn't exist), just ignore
                            pass

                if action_log.status == ActionStatus.FAILURE:
                    halt_execution = True

            else:
                # Ensure the description from the action is included in the logged params.
                log_params = action.params.copy()
                if action.description:
                    log_params["Description"] = action.description

                action_log = ActionLog(
                    status=ActionStatus.SKIPPED,
                    action_type=action.type,
                    params=log_params,
                    details=f"User skipped this action. Reason: {reason}",
                )

            action_logs.append(action_log)

        end_time = datetime.now()
        overall_status = self._determine_overall_status(action_logs)
        summary = RunSummary(
            status=overall_status,
            start_time=start_time,
            end_time=end_time,
        )

        return ExecutionReport(
            run_summary=summary,
            action_logs=action_logs,
        )
