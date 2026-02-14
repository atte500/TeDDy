from datetime import datetime

from typing import Sequence

from teddy_executor.core.domain.models import (
    ActionData,
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
        statuses = {log.status for log in action_logs}
        if ActionStatus.FAILURE in statuses:
            return RunStatus.FAILURE
        if ActionStatus.SUCCESS in statuses:
            return RunStatus.SUCCESS
        # If no failures and no successes, it means everything was skipped or is pending.
        # For a completed run, this implies all were skipped.
        return RunStatus.SUCCESS

    def execute(self, plan_content: str, interactive: bool) -> ExecutionReport:
        start_time = datetime.now()
        action_logs = []

        plan: Plan = self._plan_parser.parse(plan_content)

        for action in plan.actions:
            should_dispatch = True
            reason = ""
            if interactive and action.type.lower() != "chat_with_user":
                action_for_prompt = action  # Default to the original action

                # --- Pre-confirmation Data Normalization for Diffing ---
                # The ConsoleInteractor's diffing logic expects a flat param structure.
                # The MarkdownParser provides a different structure. To respect the ActionData
                # model's immutability, we create a temporary, normalized ActionData
                # object specifically for the prompt and interactor.
                params_for_prompt = action.params.copy()

                # Normalize file path for both CREATE and EDIT
                if action.type in ("CREATE", "EDIT"):
                    if "File Path" in params_for_prompt:
                        path_link = params_for_prompt["File Path"]
                        if isinstance(path_link, str) and path_link.endswith(")"):
                            params_for_prompt["path"] = path_link.split("(")[-1].strip(
                                ")/"
                            )
                        else:
                            params_for_prompt["path"] = path_link

                # For EDIT, flatten the 'edits' list into 'find' and 'replace'
                if action.type == "EDIT":
                    edits = params_for_prompt.get("edits")
                    if edits and isinstance(edits, list) and len(edits) > 0:
                        # The diff preview only supports the first edit block.
                        first_edit = edits[0]
                        params_for_prompt["find"] = first_edit.get("find")
                        params_for_prompt["replace"] = first_edit.get("replace")

                # Reconstruct an ActionData for the prompt if params were changed
                if params_for_prompt != action.params:
                    action_for_prompt = ActionData(
                        type=action.type,
                        params=params_for_prompt,
                        description=action.description,
                    )
                # --- End Normalization ---

                # Build a more descriptive, multi-line prompt for readability
                prompt_parts = [
                    "---",
                    f"Action: {action_for_prompt.type}",
                ]
                if action_for_prompt.description:
                    prompt_parts.append(f"Description: {action_for_prompt.description}")

                # Use a cleaner representation of params from the (potentially normalized) action
                param_str = "\n".join(
                    f"  - {k}: {v}" for k, v in action_for_prompt.params.items()
                )
                prompt_parts.append("Parameters:")
                prompt_parts.append(param_str)
                prompt_parts.append("---\nApprove action?")

                prompt = "\n".join(prompt_parts)
                should_dispatch, reason = self._user_interactor.confirm_action(
                    action=action_for_prompt, action_prompt=prompt
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

            else:
                action_log = ActionLog(
                    status=ActionStatus.SKIPPED,
                    action_type=action.type,
                    params=action.params,
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
