import re
from pathlib import Path
from typing import Any, Optional

import yaml
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


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

        # Determine agent name for progress message
        agent_name = "pathfinder"
        meta_path = (turn_p / "meta.yaml").as_posix()
        if self._file_system_manager.path_exists(meta_path):
            content = self._file_system_manager.read_file(meta_path)
            meta = yaml.safe_load(str(content)) or {}
            if isinstance(meta, dict):
                agent_name = meta.get("agent_name", agent_name)

        # Display progress right before generating plan
        import os

        if os.getenv("TEDDY_SHOWCASE") == "1":
            from prototypes.slice_00_05_logic import generate_plan_sequenced

            plan_path, turn_cost = generate_plan_sequenced(
                self._planning_service,
                self._user_interactor,
                resolved_message,
                turn_dir,
                context_files,
                agent_name,
            )
        else:
            msg = f"[cyan][{turn_p.name}] Planning Turn with {agent_name}...[/cyan]"
            self._user_interactor.display_message(msg)

            plan_path, turn_cost = self._planning_service.generate_plan(
                user_message=resolved_message,
                turn_dir=turn_dir,
                context_files=context_files,
            )

        # Handle planning cancellation/empty input
        if plan_path is None:
            return "CANCELLED"

        self._display_planning_telemetry(turn_dir, plan_path, turn_cost)

        # Dynamic Renaming Logic for Turn 1
        turn_p = Path(turn_dir)
        session_folder_name = turn_p.parent.name

        # Strip prefix to check if it's an auto-generated session name
        clean_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder_name)

        if turn_p.name == "01" and clean_name.startswith("session-"):
            renamed = self._handle_dynamic_rename(plan_path)
            return renamed or session_folder_name

        return session_folder_name

    def _display_planning_telemetry(
        self, turn_dir: str, plan_path: str, turn_cost: float
    ):
        import os

        dim_style = "dim" if os.getenv("TEDDY_SHOWCASE") != "1" else "bright_black"

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

        self._user_interactor.display_message(
            f"[{dim_style}]  Model: {model}[/{dim_style}]"
        )
        self._user_interactor.display_message(
            f"[{dim_style}]  Context: {raw_token_count / 1000:.1f}k tokens[/{dim_style}]"
        )
        self._user_interactor.display_message(
            f"[{dim_style}]  Session Cost: ${cumulative_cost:.4f}[/{dim_style}]\n"
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
                prev_report_path = turn_path.parent / prev_turn_name / "report.md"
                if self._file_system_manager.path_exists(prev_report_path.as_posix()):
                    content = self._file_system_manager.read_file(
                        prev_report_path.as_posix()
                    )
                    return extract_markdown_section(content, "User Request")
        except (ValueError, TypeError):
            pass
        return None

    def _handle_dynamic_rename(self, plan_path: str) -> Optional[str]:
        """Renames the session based on the plan title."""
        content = self._file_system_manager.read_file(plan_path)
        match = re.search(r"^#\s*(?:Plan:)?\s*(.*)$", content, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            new_name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            if new_name:
                old_name = Path(plan_path).parent.parent.name
                try:
                    new_path = self._session_service.rename_session(old_name, new_name)
                    return Path(new_path).name
                except ValueError:
                    pass
        return None
