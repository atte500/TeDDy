import logging
from pathlib import Path
from typing import Any, Optional

import yaml
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

        self._display_planning_telemetry(turn_dir, plan_path, turn_cost)

        return Path(turn_dir).parent.name

    def _display_planning_telemetry(
        self, turn_dir: str, plan_path: str, turn_cost: float
    ):
        def safe_float(v: Any, default: float = 0.0) -> float:
            try:
                if hasattr(v, "__float__"):
                    return float(v)
                return float(str(v))
            except (TypeError, ValueError):
                return default

        meta_content = self._file_system_manager.read_file(f"{turn_dir}/meta.yaml")
        meta_loaded = yaml.safe_load(str(meta_content))
        meta = meta_loaded if isinstance(meta_loaded, dict) else {}

        model = str(meta.get("model", "unknown"))

        # Arithmetic and formatting must be robust to MagicMocks leaked in tests
        raw_token_count = safe_float(meta.get("token_count", 0))
        # Cumulative cost in meta for current turn doesn't include current turn yet
        cumulative_cost = safe_float(meta.get("cumulative_cost", 0.0)) + safe_float(
            turn_cost
        )

        # Scenario: Session Visibility & Natural Language (Blue/Magenta Telemetry)
        # Use sys.stderr for telemetry to ensure it's visible even when stdout is piped/clean
        self._user_interactor.display_message(
            f"[blue]• Model:[/blue] [magenta]{model}[/magenta]"
        )
        self._user_interactor.display_message(
            f"[blue]• Context:[/blue] [magenta]{raw_token_count / 1000:.1f}k tokens[/magenta]"
        )
        self._user_interactor.display_message(
            f"[blue]• Session Cost:[/blue] [magenta]${cumulative_cost:.4f}[/magenta]\n"
        )

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
