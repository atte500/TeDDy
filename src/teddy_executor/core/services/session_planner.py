import logging
from pathlib import Path
from typing import Optional

from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager

logger = logging.getLogger(__name__)


class SessionPlanner:
    """Handles interactive turn planning and dynamic session renaming."""

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        planning_service,
        user_interactor,
        session_service,
    ):
        self._file_system_manager = file_system_manager
        self._planning_service = planning_service
        self._user_interactor = user_interactor
        self._session_service = session_service

    def trigger_new_plan(
        self, turn_dir: str, message: Optional[str] = None
    ) -> Optional[str]:
        """Prompts user and triggers planning. Returns session name on success."""
        # Note: PlanningService.generate_plan handles tiered message resolution
        # via PromptManager (CLI -> initial_request.md -> Prompt).
        resolved_message = message
        # We pass it to generate_plan which handles the resolution and hint.

        plan_path, turn_cost = self._planning_service.generate_plan(
            user_message=resolved_message,
            turn_dir=turn_dir,
        )

        # Handle planning cancellation/empty input
        if plan_path is None:
            return "CANCELLED"

        return Path(turn_dir).parent.name
