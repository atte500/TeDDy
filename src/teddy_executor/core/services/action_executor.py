from typing import Optional

from teddy_executor.core.domain.models import (
    ActionLog,
    ActionStatus,
    ChangeSet,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.services.action_diff_manager import ActionDiffManager
from teddy_executor.core.services.action_changeset_builder import ActionChangeSetBuilder
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IFileSystemManager,
    IUserInteractor,
)
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


# Constant for perfect match detection to avoid floating point noise
PERFECT_MATCH_THRESHOLD = 0.99999


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
        config_service: IConfigService,
    ):
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor
        self._file_system_manager = file_system_manager
        self._changeset_builder = ActionChangeSetBuilder(
            file_system_manager, config_service, edit_simulator
        )

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

    def _intercept_control_flow_action(
        self, action, is_session: bool = False
    ) -> ActionLog | None:
        """Intercepts control flow actions in the manual CLI workflow."""
        action_type = action.type.upper()

        if action_type == "PRUNE" and not is_session:
            return self._handle_skipped_action(
                action,
                "PRUNE actions are automatically skipped in manual mode to prevent workspace corruption. PRUNE is only active within TeDDy sessions.",
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
        return self._changeset_builder.create_change_set(action)

    def _get_interactive_confirmation(self, action) -> tuple[bool, str]:
        """Prompts the user for confirmation of an action."""
        prompt = ActionChangeSetBuilder.format_action_prompt(action)

        change_set = self._create_change_set(action)

        return self._user_interactor.confirm_action(
            action=action, action_prompt=prompt, change_set=change_set
        )

    def confirm_and_dispatch(
        self,
        action,
        interactive: bool,
        total_actions: int,
        agent_name: Optional[str] = None,
        is_session: bool = False,
    ) -> ActionLog:
        """Handles user confirmation and dispatches a single action."""
        if isolation_log := self._check_action_isolation(action, total_actions):
            return isolation_log

        if intercepted_log := self._intercept_control_flow_action(
            action, is_session=is_session
        ):
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

        action_log = self._action_dispatcher.dispatch_and_execute(
            action, agent_name=agent_name
        )

        if action_log.status == ActionStatus.FAILURE:
            return self._enrich_failed_log(action, action_log)

        return ActionDiffManager.inject_diff(action, action_log, change_set)

    def handle_skipped_action(self, action, reason: str) -> ActionLog:
        """Public method for skipping actions."""
        return self._handle_skipped_action(action, reason)
