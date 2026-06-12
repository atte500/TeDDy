import re
import yaml
from pathlib import Path
from typing import Set, Dict, Any

from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository


class SessionRepository(ISessionRepository):
    """
    Handles low-level filesystem lookups and path resolution for TeDDy sessions.
    """

    def __init__(self, file_system_manager: IFileSystemManager):
        self._file_system_manager = file_system_manager

    def path_exists(self, path: str) -> bool:
        """Checks if a path exists on the filesystem."""
        return self._file_system_manager.path_exists(path)

    def list_directory(self, path: str) -> list[str]:
        """Lists the contents of a directory."""
        return self._file_system_manager.list_directory(path)

    def create_turn_directory(self, turn_dir: str) -> None:
        """Ensures a turn directory exists."""
        self._file_system_manager.create_directory(turn_dir)

    def _strip_prefix(self, name: str) -> str:
        """Strips the YYYYMMDD_HHMMSS- prefix from a session folder name."""
        return re.sub(r"^\d{8}_\d{6}-", "", name)

    def get_latest_session_name(self) -> str:
        """Identifies the most recently modified session (returns folder name)."""
        sessions_root = ".teddy/sessions"
        if not self._file_system_manager.path_exists(sessions_root):
            raise ValueError("No sessions found.")

        sessions = self._file_system_manager.list_directory(sessions_root)
        if not sessions:
            raise ValueError("No sessions found.")

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
        """Climbs the directory tree to find the session (returns folder name)."""
        # Convert to relative path if absolute, relative to CWD
        try:
            p = Path(path).resolve().relative_to(Path.cwd())
        except ValueError:
            p = Path(path)

        for parent in [p] + list(p.parents):
            if parent.parent.name == "sessions" and ".teddy" in parent.parts:
                return parent.name

        if self._file_system_manager.path_exists(f".teddy/sessions/{path}"):
            return path

        raise ValueError(f"Could not resolve session from path: {path}")

    def is_valid_path(self, path_str: str) -> bool:
        """Heuristic to check if a string is a plausible file path."""
        if (
            not path_str
            or path_str.startswith("#")
            or "**" in path_str
            or ":" in path_str
            and not path_str.startswith(("http:", "https:"))
        ):
            return False
        # Markdown structural elements often start with '-' or '*' followed by bold markers
        if (
            path_str.startswith("- **")
            or path_str.startswith("* **")
            or "Command:" in path_str
        ):
            return False
        return True

    def read_context_file(self, path: str) -> Set[str]:
        """Reads a context file robustly."""
        try:
            if not self._file_system_manager.path_exists(path):
                return set()
            content = self._file_system_manager.read_file(path)
            lines = {line.strip() for line in content.splitlines() if line.strip()}
            return {line for line in lines if self.is_valid_path(line)}
        except (FileNotFoundError, OSError):
            return set()

    def to_root_relative(self, turn_dir: Path, filename: str) -> str:
        """Calculates a root-relative path for a file within a turn directory."""
        file_path = turn_dir.joinpath(filename)
        path_parts = list(file_path.parts)

        if ".teddy" in path_parts:
            idx = path_parts.index(".teddy")
            return "/".join(path_parts[idx:])

        if "sessions" in path_parts:
            idx = path_parts.index("sessions")
            return ".teddy/" + "/".join(path_parts[idx:])

        return f"{turn_dir.name}/{filename}"

    def load_meta(self, turn_dir: str) -> Dict[str, Any]:
        """Loads and parses meta.yaml for a turn."""
        content = self._file_system_manager.read_file(f"{turn_dir}/meta.yaml")
        meta = yaml.safe_load(str(content))
        return meta if isinstance(meta, dict) else {}

    def save_meta(self, path: str, data: Dict[str, Any]) -> None:
        """Serializes and persists metadata to the filesystem."""
        from teddy_executor.core.utils.serialization import scrub_dict_for_serialization

        serializable = scrub_dict_for_serialization(data)
        self._file_system_manager.write_file(path, yaml.dump(serializable))

    def copy_prompt(self, src_dir: str, dest_dir: str, agent: str) -> None:
        """Copies an agent prompt file between turn directories."""
        if not self._file_system_manager.path_exists(src_dir):
            return
        for f in self._file_system_manager.list_directory(src_dir):
            if Path(f).stem == agent:
                src_path = f"{src_dir}/{f}"
                if self._file_system_manager.path_exists(src_path):
                    content = self._file_system_manager.read_file(src_path)
                    self._file_system_manager.write_file(f"{dest_dir}/{f}", content)
                    return

    def get_latest_turn(self, session_name: str) -> str:
        """Identifies and returns the path to the latest turn in a session."""
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

    def rename_session(self, old_name: str, new_name: str) -> str:
        """Renames a session directory on the filesystem."""
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

    def resolve_context_paths(self, plan_path: str) -> Dict[str, list[str]]:
        """Locates and returns the contents of session and turn context files."""
        plan_p = Path(plan_path)
        turn_dir = plan_p.parent
        session_dir = turn_dir.parent

        session_context_path = (session_dir / "session.context").as_posix()
        turn_context_path = (turn_dir / "turn.context").as_posix()

        return {
            "Session": sorted(list(self.read_context_file(session_context_path))),
            "Turn": sorted(list(self.read_context_file(turn_context_path))),
        }
