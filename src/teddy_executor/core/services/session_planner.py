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
        # 1. Tiered Message Resolution
        # If CLI message is provided, we use it directly.
        # Otherwise, we look at the previous turn's report.
        resolved_message = message
        if not resolved_message:
            resolved_message = self._resolve_message_from_previous_turn(turn_dir)

        # Note: PlanningService.generate_plan handles Priority 2 (local report) and 3 (prompt).
        # We pass it to generate_plan which handles the resolution and hint.

        # Resolve context files
        turn_p = Path(turn_dir)
        session_dir = turn_p.parent
        context_files = {
            "Session": [(session_dir / "session.context").as_posix()],
            "Turn": [(turn_p / "turn.context").as_posix()],
        }

        plan_path, turn_cost = self._planning_service.generate_plan(
            user_message=resolved_message,
            turn_dir=turn_dir,
            context_files=context_files,
        )

        # Handle planning cancellation/empty input
        if plan_path is None:
            return "CANCELLED"

        return Path(turn_dir).parent.name

    def _resolve_message_from_previous_turn(self, turn_dir: str) -> Optional[str]:
        """Specialized session logic to look back at the previous turn's report."""
        from teddy_executor.core.utils.markdown import extract_markdown_section

        turn_path = Path(turn_dir)
        try:
            # Turn names are numeric strings (01, 02...)
            turn_idx = int(turn_path.name)
            if turn_idx > 1:
                prev_turn_name = f"{turn_idx - 1:02d}"
                prev_turn_dir = turn_path.parent / prev_turn_name
                prev_report_path = prev_turn_dir / "report.md"

                if self._file_system_manager.path_exists(prev_report_path.as_posix()):
                    # R-10-12: If successful, return empty string to signal continuation.
                    # This silences the prompt while keeping the agent running.
                    content = self._file_system_manager.read_file(
                        prev_report_path.as_posix()
                    )

                    is_success = "- **Overall Status:** SUCCESS" in content
                    if is_success:
                        return ""

                    return extract_markdown_section(content, "User Request")
        except (ValueError, TypeError) as e:
            logger.debug(
                "Failed to resolve message from previous turn in %s: %s", turn_dir, e
            )
        return None
