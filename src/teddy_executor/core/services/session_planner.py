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
        if not message:
            message = self._user_interactor.ask_question(
                "Enter your instructions for the AI"
            )
        if not message:
            return None

        # Add helpful hint for alignment
        hint = "\n\n*(Stop to reply to this user request and ensure alignment before proceeding)*"
        message += hint

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
        msg = f"[cyan][{turn_p.name}] Planning Turn with {agent_name}...[/cyan]"
        self._user_interactor.display_message(msg)

        plan_path, turn_cost = self._planning_service.generate_plan(
            user_message=message, turn_dir=turn_dir, context_files=context_files
        )

        self._display_planning_telemetry(turn_dir, plan_path, turn_cost)

        # Dynamic Renaming Logic for Turn 1
        turn_p = Path(turn_dir)
        session_name = turn_p.parent.name
        if turn_p.name == "01" and session_name.startswith("session-"):
            renamed = self._handle_dynamic_rename(plan_path)
            return renamed or session_name

        return session_name

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

        self._user_interactor.display_message(f"[dim]  Model: {model}[/dim]")
        self._user_interactor.display_message(
            f"[dim]  Context: {raw_token_count / 1000:.1f}k tokens[/dim]"
        )
        self._user_interactor.display_message(
            f"[dim]  Session Cost: ${cumulative_cost:.4f}[/dim]\n"
        )

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
                    self._session_service.rename_session(old_name, new_name)
                    return new_name
                except ValueError:
                    pass
        return None
