import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import yaml
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.prompts import find_prompt_content


class SessionService(ISessionManager):
    """
    Service for managing session directories and metadata.
    """

    def __init__(self, file_system_manager: IFileSystemManager):
        self._file_system_manager = file_system_manager

    def create_session(self, name: str, agent_name: str) -> str:
        """
        Initializes a new session directory and bootstraps it for Turn 1.
        """
        session_root = f".teddy/sessions/{name}"
        turn_dir = f"{session_root}/01"

        self._file_system_manager.create_directory(turn_dir)

        # 1. Seed session.context from init.context
        init_context = self._file_system_manager.read_file(".teddy/init.context")
        # Strip comments as per specification
        clean_context = "\n".join(
            [
                line
                for line in init_context.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        )
        self._file_system_manager.write_file(
            f"{session_root}/session.context", clean_context
        )

        # 2. Populate system_prompt.xml
        prompt_content = find_prompt_content(agent_name)
        if not prompt_content:
            raise ValueError(f"Agent prompt '{agent_name}' not found.")
        self._file_system_manager.write_file(
            f"{turn_dir}/system_prompt.xml", prompt_content
        )

        # 3. Create meta.yaml
        meta_data = {
            "turn_id": "01",
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._file_system_manager.write_file(
            f"{turn_dir}/meta.yaml", yaml.dump(meta_data)
        )

        return session_root

    def get_latest_turn(self, session_name: str) -> str:
        """
        Identifies and returns the latest turn directory in the specified session.
        """
        session_root = f".teddy/sessions/{session_name}"
        try:
            items = self._file_system_manager.list_directory(session_root)
        except FileNotFoundError:
            raise ValueError(f"Session '{session_name}' not found.")

        # Filter for zero-padded numeric directories (e.g., '01', '02')
        turns = [item for item in items if item.isdigit()]
        if not turns:
            raise ValueError(f"No turns found in session '{session_name}'.")

        latest_turn_id = sorted(turns)[-1]
        return f"{session_root}/{latest_turn_id}"

    def get_session_state(self, session_name: str) -> tuple[SessionState, str]:
        """
        Determines the state of the session and returns the state and the path
        to the latest turn.
        """
        latest_turn_path = self.get_latest_turn(session_name)

        plan_exists = self._file_system_manager.path_exists(
            f"{latest_turn_path}/plan.md"
        )
        report_exists = self._file_system_manager.path_exists(
            f"{latest_turn_path}/report.md"
        )

        if report_exists:
            return SessionState.COMPLETE_TURN, latest_turn_path
        if plan_exists:
            return SessionState.PENDING_PLAN, latest_turn_path

        return SessionState.EMPTY, latest_turn_path

    def _extract_resource_path(self, resource_str: str) -> str:
        """Extracts the path from a Markdown link or returns the string if not a link."""
        match = re.search(r"\[.*\]\((.*)\)", resource_str)
        if match:
            path = match.group(1)
            return path.lstrip("/")
        return resource_str.strip()

    def _read_context_file(self, path: str) -> set[str]:
        """Reads a context file robustly and returns a set of non-empty paths."""
        try:
            if not self._file_system_manager.path_exists(path):
                return set()
            content = self._file_system_manager.read_file(path)
            return {line.strip() for line in content.splitlines() if line.strip()}
        except (FileNotFoundError, OSError):
            return set()

    def transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        is_validation_failure: bool = False,
    ) -> str:
        """
        Calculates and creates the next turn directory based on the current turn
        and the outcome of its plan.
        """
        current_turn_dir = Path(plan_path).parent.as_posix()
        session_dir = Path(current_turn_dir).parent.as_posix()

        # 1. Read current metadata and context
        meta_content = self._file_system_manager.read_file(
            f"{current_turn_dir}/meta.yaml"
        )
        current_meta = yaml.safe_load(meta_content) or {}
        current_turn_id = current_meta.get("turn_id")

        # Seed next context with current turn's context
        next_context_paths = self._read_context_file(f"{current_turn_dir}/turn.context")

        # 2. Calculate next turn
        current_turn_num = int(Path(current_turn_dir).name)
        next_turn_num = current_turn_num + 1
        next_turn_id = f"{next_turn_num:02d}"
        next_turn_dir = f"{session_dir}/{next_turn_id}"

        # 3. Initialize next turn directory
        self._file_system_manager.create_directory(next_turn_dir)

        # 4. Copy system_prompt.xml
        prompt_content = self._file_system_manager.read_file(
            f"{current_turn_dir}/system_prompt.xml"
        )
        self._file_system_manager.write_file(
            f"{next_turn_dir}/system_prompt.xml", prompt_content
        )

        # 5. Create next meta.yaml
        next_meta = {
            "turn_id": next_turn_id,
            "parent_turn_id": current_turn_id,
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._file_system_manager.write_file(
            f"{next_turn_dir}/meta.yaml", yaml.dump(next_meta)
        )

        # 6. Apply READ/PRUNE side effects
        if execution_report:
            for action in execution_report.original_actions:
                resource = action.params.get("resource") or action.params.get(
                    "Resource"
                )
                if not resource:
                    continue

                extracted_path = self._extract_resource_path(resource)
                if action.type == ActionType.READ.value:
                    next_context_paths.add(extracted_path)
                elif action.type == ActionType.PRUNE.value:
                    next_context_paths.discard(extracted_path)

        # 7. Add current report.md to next context
        if not is_validation_failure:
            relative_report_path = f"{Path(current_turn_dir).name}/report.md"
            next_context_paths.add(relative_report_path)

        # 8. Write next turn.context
        sorted_paths = sorted(list(next_context_paths))
        self._file_system_manager.write_file(
            f"{next_turn_dir}/turn.context", "\n".join(sorted_paths)
        )

        return next_turn_dir

    def rename_session(self, old_name: str, new_name: str) -> str:
        """
        Safely renames a session directory on the filesystem.
        """
        old_path = f".teddy/sessions/{old_name}"
        new_path = f".teddy/sessions/{new_name}"

        if not self._file_system_manager.path_exists(old_path):
            raise ValueError(f"Session '{old_name}' not found.")
        if self._file_system_manager.path_exists(new_path):
            raise ValueError(f"Session '{new_name}' already exists.")

        self._file_system_manager.move_directory(old_path, new_path)
        return new_path

    def resolve_context_paths(self, plan_path: str) -> dict[str, list[str]]:
        """
        Locates session.context and turn.context relative to plan_path
        and returns their contents.
        """
        plan_p = Path(plan_path)
        turn_dir = plan_p.parent
        session_dir = turn_dir.parent

        session_context_path = (session_dir / "session.context").as_posix()
        turn_context_path = (turn_dir / "turn.context").as_posix()

        return {
            "Session": sorted(list(self._read_context_file(session_context_path))),
            "Turn": sorted(list(self._read_context_file(turn_context_path))),
        }

    def get_latest_session_name(self) -> str:
        """
        Identifies and returns the name of the most recently modified session.
        """
        sessions_root = ".teddy/sessions"
        if not self._file_system_manager.path_exists(sessions_root):
            raise ValueError("No sessions found.")

        sessions = self._file_system_manager.list_directory(sessions_root)
        if not sessions:
            raise ValueError("No sessions found.")

        # Sort by mtime descending
        session_stats = []
        for name in sessions:
            path = f"{sessions_root}/{name}"
            try:
                mtime = self._file_system_manager.get_mtime(path)
                session_stats.append((name, mtime))
            except (FileNotFoundError, OSError):
                continue

        if not session_stats:
            raise ValueError("No valid sessions found.")

        session_stats.sort(key=lambda x: x[1], reverse=True)
        return session_stats[0][0]

    def resolve_session_from_path(self, path: str) -> str:
        """
        Resolves a session name from a given path (session root, turn dir, or file).
        """
        p = Path(path).resolve()
        # Climb up parents looking for '.teddy/sessions'
        for parent in [p] + list(p.parents):
            if (
                parent.parent.name == "sessions"
                and parent.parent.parent.name == ".teddy"
            ):
                return parent.name

        # If not found via parents, check if the path itself IS a session name
        # (Legacy behavior for explicit name passing)
        if self._file_system_manager.path_exists(f".teddy/sessions/{path}"):
            return path

        raise ValueError(f"Could not resolve session from path: {path}")
