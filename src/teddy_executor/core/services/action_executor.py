import hashlib
import logging
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

logger = logging.getLogger(__name__)

# Constant for perfect match detection to avoid floating point noise
PERFECT_MATCH_THRESHOLD = 0.99999


class ActionExecutor:
    """
    Handles the execution logic for a single action, including isolation,
    interception, and user confirmation.
    """

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
        self._file_hashes: dict[str, str] = {}

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
            modified=action.modified,
            modified_fields=action.modified_fields,
        )

    def _compute_file_hash(self, path: str) -> str:
        """Computes SHA256 hash of file content for mid-execution consistency checks."""
        content = self._file_system_manager.read_file(path)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

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
                modified=action_log.modified,
                modified_fields=action_log.modified_fields,
            )
        except Exception as e:
            logger.debug(
                "Failed to enrich failed log with file content for %s: %s", path, e
            )
            return action_log

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

    def confirm_and_dispatch(  # noqa: PLR0913, C901
        self,
        action,
        interactive: bool,
        total_actions: int,
        agent_name: Optional[str] = None,
        is_session: bool = False,
        skip_isolation: bool = False,
    ) -> tuple[ActionLog, str]:
        """Handles user confirmation and dispatches a single action."""
        # Capture the change set BEFORE execution for diff reporting
        change_set = self._create_change_set(action)

        should_dispatch, reason = True, ""
        # Communication actions (MESSAGE) bypass the interactive confirmation
        # to ensure a fluid conversational flow.
        is_communication = action.type.upper() == "MESSAGE"

        if interactive and not is_communication:
            should_dispatch, reason = self._get_interactive_confirmation(action)

        if not should_dispatch:
            return (
                self._handle_skipped_action(
                    action, f"User skipped this action. Reason: {reason}"
                ),
                "",
            )

        # Mid-execution consistency: pre-check hash for EDIT actions
        path = action.params.get("path")
        if action.type.upper() == "EDIT" and path and path in self._file_hashes:
            try:
                current_hash = self._compute_file_hash(path)
                if current_hash != self._file_hashes[path]:
                    logger.error(
                        "EDIT pre-check failed: file content modified during "
                        "execution for %s",
                        path,
                    )
                    return (
                        ActionLog(
                            status=ActionStatus.FAILURE,
                            action_type="EDIT",
                            params=action.params.copy(),
                            details="File content modified during execution",
                        ),
                        reason,
                    )
            except OSError:  # safe to ignore
                # If we can't read the file, proceed with normal dispatch
                pass

        action_log = self._action_dispatcher.dispatch_and_execute(
            action, agent_name=agent_name
        )

        if action_log.status == ActionStatus.FAILURE:
            return self._enrich_failed_log(action, action_log), reason

        # Post-dispatch: update hash for EDIT, clear for EXECUTE
        if action.type.upper() == "EDIT" and path:
            try:
                self._file_hashes[path] = self._compute_file_hash(path)
            except OSError:  # safe to ignore
                pass
        elif action.type.upper() == "EXECUTE":
            self._file_hashes.clear()

        # For success, we still want to return the message captured via 'm'
        return (
            ActionDiffManager.inject_diff(action, action_log, change_set),
            reason,
        )

    def handle_skipped_action(self, action, reason: str) -> ActionLog:
        """Public method for skipping actions."""
        return self._handle_skipped_action(action, reason)

    def handle_failed_action(self, action, details: str) -> ActionLog:
        """Creates an ActionLog for an action that failed during preparation."""
        return self._create_intercepted_log(action, ActionStatus.FAILURE, details)

    def reset_file_hashes(self) -> None:
        """
        Clears all stored file hashes. Called at the start of each plan execution
        to prevent stale hashes from previous turns from causing false pre-check failures.
        """
        self._file_hashes.clear()
