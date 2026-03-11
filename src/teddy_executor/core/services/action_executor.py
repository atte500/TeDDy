from pathlib import Path
from teddy_executor.core.domain.models import (
    ActionLog,
    ActionStatus,
    ChangeSet,
)
from teddy_executor.core.utils.diff import generate_unified_diff
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


class ActionExecutor:
    """
    Handles the execution logic for a single action, including isolation,
    interception, and user confirmation.
    """

    TERMINAL_ACTIONS = ("PROMPT", "INVOKE", "RETURN")

    def __init__(
        self,
        action_dispatcher: ActionDispatcher,
        user_interactor: IUserInteractor,
        file_system_manager: IFileSystemManager,
        edit_simulator: IEditSimulator,
    ):
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor
        self._file_system_manager = file_system_manager
        self._edit_simulator = edit_simulator

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

    def _check_action_isolation(self, action, total_actions: int) -> ActionLog | None:
        """Ensures terminal actions are executed in isolation."""
        if total_actions > 1 and action.type.upper() in self.TERMINAL_ACTIONS:
            return self._handle_skipped_action(
                action,
                "Action must be executed in isolation to ensure state consistency.",
            )
        return None

    def _intercept_control_flow_action(self, action) -> ActionLog | None:
        """Intercepts control flow actions in the manual CLI workflow."""
        action_type = action.type.upper()

        if action_type == "PRUNE":
            return self._handle_skipped_action(
                action,
                "Skipped: PRUNE is not supported in manual execution mode.",
            )

        if action_type in ("INVOKE", "RETURN"):
            approved, reason = self._user_interactor.confirm_manual_handoff(
                action_type=action_type,
                target_agent=action.params.get("Agent") or action.params.get("agent"),
                resources=action.params.get("handoff_resources") or [],
                message=action.params.get("message")
                or action.params.get("Message")
                or "",
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

        before_content = (
            self._file_system_manager.read_file(path_str)
            if self._file_system_manager.path_exists(path_str)
            else ""
        )
        path = Path(path_str)

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
        display_map = {"handoff_resources": "Reference Files"}
        param_str = "\n".join(
            f"  - {display_map.get(k, k)}: {v}"
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

    def confirm_and_dispatch(
        self, action, interactive: bool, total_actions: int
    ) -> ActionLog:
        """Handles user confirmation and dispatches a single action."""
        if isolation_log := self._check_action_isolation(action, total_actions):
            return isolation_log

        if intercepted_log := self._intercept_control_flow_action(action):
            return intercepted_log

        # Capture the change set BEFORE execution for diff reporting
        change_set = self._create_change_set(action)

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

        return self._inject_execution_diff(action, action_log, change_set)

    def _inject_execution_diff(self, action, action_log, change_set) -> ActionLog:
        """Injects a unified diff into the log for CREATE overwrites."""
        # Scenario 3: If it was a CREATE overwrite, ensure the report includes a diff
        if action.type.upper() != "CREATE" or action_log.status != ActionStatus.SUCCESS:
            return action_log

        # Check types to handle Mocks in tests gracefully
        if (
            not change_set
            or not isinstance(change_set.before_content, str)
            or not isinstance(change_set.after_content, str)
            or not change_set.before_content
        ):
            return action_log

        diff = generate_unified_diff(
            change_set.before_content,
            change_set.after_content,
            change_set.path.name,
        )

        if not diff:
            return action_log

        # Inject the diff into details for the reporter
        details = action_log.details
        new_details = {"diff": diff}

        if isinstance(details, dict):
            new_details.update(details)

        return ActionLog(
            status=action_log.status,
            action_type=action_log.action_type,
            params=action_log.params,
            details=new_details,
        )

    def handle_skipped_action(self, action, reason: str) -> ActionLog:
        """Public method for skipping actions."""
        return self._handle_skipped_action(action, reason)
