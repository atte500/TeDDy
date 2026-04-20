import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.prompts import find_prompt_content


from teddy_executor.core.services.session_repository import SessionRepository


class SessionService(ISessionManager):
    """
    Service for managing session directories and metadata.
    """

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        repository: SessionRepository,
    ):
        self._file_system_manager = file_system_manager
        self._repository = repository

    def create_session(self, name: str, agent_name: str) -> str:
        """
        Initializes a new session directory and bootstraps it for Turn 1.
        """
        import os

        if os.getenv("TEDDY_SHOWCASE") == "1":
            from prototypes.slice_00_05_logic import create_session_prefixed

            return create_session_prefixed(self, name, agent_name)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefixed_name = f"{timestamp}-{name}"
        session_root = f".teddy/sessions/{prefixed_name}"
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

        # 2. Populate specific agent prompt file
        prompt_content = find_prompt_content(agent_name)
        if not prompt_content:
            raise ValueError(f"Agent prompt '{agent_name}' not found.")
        self._file_system_manager.write_file(
            f"{turn_dir}/{agent_name}.xml", prompt_content
        )

        # 3. Create meta.yaml
        meta_data = {
            "turn_id": "01",
            "agent_name": agent_name,
            "cumulative_cost": 0.0,
            "turn_cost": 0.0,
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._write_meta(f"{turn_dir}/meta.yaml", meta_data)

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

    def transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        turn_cost: float = 0.0,
        is_validation_failure: bool = False,
    ) -> str:
        """
        Calculates and creates the next turn directory based on the current turn
        and the outcome of its plan.
        """
        _ = is_validation_failure
        cur_dir = Path(plan_path).parent
        session_dir = cur_dir.parent.as_posix()

        # 1. Resolve current state
        meta = self._load_meta(cur_dir.as_posix())
        next_id = f"{int(cur_dir.name) + 1:02d}"
        next_dir = f"{session_dir}/{next_id}"

        # 2. Setup next directory
        self._file_system_manager.create_directory(next_dir)
        self._copy_prompt(cur_dir.as_posix(), next_dir, meta.get("agent_name", "pf"))

        # 3. Persist metadata
        self._persist_next_meta(next_dir, next_id, meta, turn_cost)

        # 4. Handle context
        paths = self._repository.read_context_file(f"{cur_dir.as_posix()}/turn.context")
        self._apply_execution_effects(paths, execution_report)

        # Always append BOTH plan.md and report.md to the next turn's context
        # to ensure the AI has its previous intent and the resulting outcome.
        paths.add(self._to_root_relative(cur_dir, "plan.md"))
        paths.add(self._to_root_relative(cur_dir, "report.md"))

        self._file_system_manager.write_file(
            f"{next_dir}/turn.context", "\n".join(sorted(list(paths)))
        )
        return next_dir

    def _to_root_relative(self, turn_dir: Path, filename: str) -> str:
        """Calculates a root-relative path for a file within a turn directory."""
        file_path = turn_dir.joinpath(filename)
        path_parts = list(file_path.parts)

        # Primary: find the hidden .teddy directory
        if ".teddy" in path_parts:
            idx = path_parts.index(".teddy")
            return "/".join(path_parts[idx:])

        # Secondary (Tests): find the sessions/ folder
        if "sessions" in path_parts:
            idx = path_parts.index("sessions")
            return ".teddy/" + "/".join(path_parts[idx:])

        # Fallback to local turn name
        return f"{turn_dir.name}/{filename}"

    def _load_meta(self, turn_dir: str) -> Dict[str, Any]:
        """Loads and parses meta.yaml for a turn."""
        content = self._file_system_manager.read_file(f"{turn_dir}/meta.yaml")
        meta = yaml.safe_load(str(content))
        return meta if isinstance(meta, dict) else {}

    def _copy_prompt(self, src_dir: str, dest_dir: str, agent: str) -> None:
        """Copies the agent prompt file if it exists."""
        prompt_path = f"{src_dir}/{agent}.xml"
        if self._file_system_manager.path_exists(prompt_path):
            content = self._file_system_manager.read_file(prompt_path)
            self._file_system_manager.write_file(f"{dest_dir}/{agent}.xml", content)

    def _apply_execution_effects(
        self, paths: set[str], report: Optional[ExecutionReport]
    ) -> None:
        """Applies side effects from READ/PRUNE actions to the context set."""
        if not report:
            return
        for action in report.original_actions:
            resource = action.params.get("resource") or action.params.get("Resource")
            if not resource:
                continue
            path = self._extract_resource_path(resource)
            if action.type == ActionType.READ.value:
                if self._repository.is_valid_path(path):
                    paths.add(path)
            elif action.type == ActionType.PRUNE.value:
                paths.discard(path)

    def _persist_next_meta(
        self,
        next_dir: str,
        next_id: str,
        current_meta: Dict[str, Any],
        turn_cost: float,
    ) -> None:
        """Calculates and persists metadata for the next turn."""
        prev_cost = current_meta.get("cumulative_cost", 0.0)
        try:
            cumulative = float(prev_cost) + float(turn_cost)
        except (TypeError, ValueError):
            cumulative = 0.0

        meta = {
            "turn_id": next_id,
            "agent_name": current_meta.get("agent_name", "pf"),
            "cumulative_cost": cumulative,
            "parent_turn_id": current_meta.get("turn_id", "00"),
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._write_meta(f"{next_dir}/meta.yaml", meta)

    def _write_meta(self, path: str, data: Dict[str, Any]) -> None:
        """Serializes and writes meta.yaml."""
        from teddy_executor.core.utils.serialization import scrub_dict_for_serialization

        serializable = scrub_dict_for_serialization(data)
        self._file_system_manager.write_file(path, yaml.dump(serializable))

    def rename_session(self, old_name: str, new_name: str) -> str:
        """
        Safely renames a session directory on the filesystem.
        """
        # Preserve date prefix if present
        prefix_match = re.match(r"^(\d{8}_\d{6}-)", old_name)
        prefix = prefix_match.group(1) if prefix_match else ""

        # Ensure new name doesn't double-prefix
        clean_new_name = re.sub(r"^\d{8}_\d{6}-", "", new_name)

        old_path = f".teddy/sessions/{old_name}"
        new_path = f".teddy/sessions/{prefix}{clean_new_name}"

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
            "Session": sorted(
                list(self._repository.read_context_file(session_context_path))
            ),
            "Turn": sorted(list(self._repository.read_context_file(turn_context_path))),
        }

    def get_latest_session_name(self) -> str:
        """Identifies and returns the name of the latest session."""
        return self._repository.get_latest_session_name()

    async def async_transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        turn_cost: float = 0.0,
        is_validation_failure: bool = False,
    ) -> str:
        """
        Asynchronously calculates and creates the next turn directory.
        """
        raise NotImplementedError("Async transition not yet implemented.")

    def resolve_session_from_path(self, path: str) -> str:
        """Resolves a session name from a given path."""
        return self._repository.resolve_session_from_path(path)
