from datetime import datetime

from typing import Sequence

from pathlib import Path
from teddy_executor.core.domain.models import (
    ActionLog,
    ChangeSet,
    ExecutionReport,
    Plan,
    RunSummary,
    RunStatus,
    ActionStatus,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
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
        edit_simulator: IEditSimulator,
    ):
        self._plan_parser = plan_parser
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor
        self._file_system_manager = file_system_manager
        self._edit_simulator = edit_simulator

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

    def _create_intercepted_log(
        self, action, status: ActionStatus, details: str
    ) -> ActionLog:
        """Creates an ActionLog for an intercepted action (skip or handoff)."""
        log_params = action.params.copy()
        if action.description:
            log_params["Description"] = action.description
        return ActionLog(
            status=status,
            action_type=action.type,
            params=log_params,
            details=details,
        )

    def _handle_skipped_action(self, action, reason: str) -> ActionLog:
        """Creates an ActionLog for a skipped action."""
        return self._create_intercepted_log(action, ActionStatus.SKIPPED, reason)

    def _enrich_failed_log(self, action, action_log: ActionLog) -> ActionLog:
        """If a CREATE or EDIT action failed, enrich the log with file content."""
        if action.type not in ("CREATE", "EDIT"):
            return action_log

        path = action.params.get("path") or action.params.get("File Path")
        if not path:
            return action_log

        try:
            content = self._file_system_manager.read_file(path)
            new_details = (
                action_log.details
                if isinstance(action_log.details, dict)
                else {"original_details": action_log.details}
            )
            new_details["content"] = content
            return ActionLog(
                status=action_log.status,
                action_type=action_log.action_type,
                params=action_log.params,
                details=new_details,
            )
        except Exception:
            return action_log

    def _intercept_control_flow_action(
        self, action, interactive: bool
    ) -> ActionLog | None:
        """Intercepts control flow actions in the manual CLI workflow."""
        action_type = action.type.upper()

        # Scenario 1: PRUNE in Non-Interactive Mode
        if action_type == "PRUNE":
            return self._handle_skipped_action(
                action,
                "Skipped: PRUNE is not supported in manual execution mode.",
            )

        # Scenario 2: INVOKE/RETURN in Non-Interactive Mode
        if action_type in ("INVOKE", "RETURN"):
            # If not interactive (--yes), auto-approve. Otherwise, prompt user.
            approved, reason = (
                (True, "")
                if not interactive
                else self._user_interactor.confirm_manual_handoff(
                    action_type=action_type,
                    target_agent=action.params.get("Agent")
                    or action.params.get("agent"),
                    resources=action.params.get("Handoff Resources")
                    or action.params.get("handoff_resources")
                    or [],
                    message=action.params.get("message")
                    or action.params.get("Message")
                    or "",
                )
            )

            if approved:
                return self._create_intercepted_log(
                    action, ActionStatus.SUCCESS, "Manual handoff approved by user."
                )
            else:
                return self._create_intercepted_log(
                    action,
                    ActionStatus.FAILURE,
                    f"Manual handoff rejected by user: {reason}",
                )

        return None

    def _create_change_set(self, action) -> ChangeSet | None:
        """Creates a ChangeSet for file operations."""
        if action.type.upper() not in ("CREATE", "EDIT"):
            return None

        path_str = action.params.get("path") or action.params.get("File Path")
        if not path_str:
            return None

        path = Path(path_str)
        before_content = (
            self._file_system_manager.read_file(path_str) if path.exists() else ""
        )

        if action.type.upper() == "EDIT":
            after_content = self._edit_simulator.simulate_edits(
                before_content, action.params.get("edits", [])
            )
        else:  # CREATE
            after_content = action.params.get("content", "")

        return ChangeSet(
            path=path,
            before_content=before_content,
            after_content=after_content,
            action_type=action.type.upper(),
        )

    def _get_interactive_confirmation(self, action) -> tuple[bool, str]:
        """Prompts the user for confirmation of an action."""
        prompt_parts = [
            "---",
            f"Action: {action.type}",
            f"Description: {action.description}" if action.description else "",
        ]
        param_str = "\n".join(
            f"  - {k}: {v}"
            for k, v in action.params.items()
            if k.lower() not in ("edits", "content")
        )
        if param_str:
            prompt_parts.extend(["Parameters:", param_str])
        prompt_parts.append("---")
        prompt = "\n".join(filter(None, prompt_parts))

        change_set = self._create_change_set(action)

        return self._user_interactor.confirm_action(
            action=action, action_prompt=prompt, change_set=change_set
        )

    def _confirm_and_dispatch_action(self, action, interactive: bool) -> ActionLog:
        """Handles user confirmation and dispatches a single action."""
        # For the stateless, manual CLI workflow, always intercept these actions.
        # The future stateful session runner will use a different orchestrator or flag.
        if intercepted_log := self._intercept_control_flow_action(action, interactive):
            return intercepted_log

        should_dispatch, reason = True, ""
        if interactive and action.type.lower() != "prompt":
            should_dispatch, reason = self._get_interactive_confirmation(action)

        if not should_dispatch:
            return self._handle_skipped_action(
                action, f"User skipped this action. Reason: {reason}"
            )

        action_log = self._action_dispatcher.dispatch_and_execute(action)

        if action_log.status == ActionStatus.FAILURE:
            return self._enrich_failed_log(action, action_log)

        return action_log

    def execute(self, plan: Plan, interactive: bool) -> ExecutionReport:
        start_time = datetime.now()
        action_logs = []
        halt_execution = False

        for action in plan.actions:
            if halt_execution:
                reason = "Skipped because a previous action failed."
                self._user_interactor.notify_skipped_action(action, reason)
                action_logs.append(self._handle_skipped_action(action, reason))
                continue

            action_log = self._confirm_and_dispatch_action(action, interactive)
            action_logs.append(action_log)

            if action_log.status == ActionStatus.FAILURE:
                halt_execution = True

        end_time = datetime.now()
        summary = RunSummary(
            status=self._determine_overall_status(action_logs),
            start_time=start_time,
            end_time=end_time,
        )

        return ExecutionReport(run_summary=summary, action_logs=action_logs)
