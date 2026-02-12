from datetime import datetime

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

    def execute(self, plan_content: str, interactive: bool) -> ExecutionReport:
        start_time = datetime.now()
        action_logs = []
        overall_status: RunStatus = RunStatus.SUCCESS

        plan: Plan = self._plan_parser.parse(plan_content)

        for action in plan.actions:
            should_dispatch = True
            reason = ""
            if interactive and action.type != "chat_with_user":
                # Build a more descriptive, multi-line prompt for readability
                # and correctly include the description.
                prompt_parts = [
                    "---",
                    f"Action: {action.type}",
                ]
                if action.description:
                    prompt_parts.append(f"Description: {action.description}")

                # Use a cleaner representation of params
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
                    path = action.params.get("path")
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
