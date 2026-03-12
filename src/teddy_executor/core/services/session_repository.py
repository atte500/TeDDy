from pathlib import Path
from typing import Set


class SessionRepository:
    """
    Handles low-level filesystem lookups and path resolution for TeDDy sessions.
    """

    def __init__(self, file_system_manager):
        self._file_system_manager = file_system_manager

    def get_latest_session_name(self) -> str:
        """Identifies the most recently modified session."""
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
        """Climbs the directory tree to find the session name."""
        p = Path(path).resolve()
        for parent in [p] + list(p.parents):
            if (
                parent.parent.name == "sessions"
                and parent.parent.parent.name == ".teddy"
            ):
                return parent.name

        if self._file_system_manager.path_exists(f".teddy/sessions/{path}"):
            return path

        raise ValueError(f"Could not resolve session from path: {path}")

    def read_context_file(self, path: str) -> Set[str]:
        """Reads a context file robustly."""
        try:
            if not self._file_system_manager.path_exists(path):
                return set()
            content = self._file_system_manager.read_file(path)
            return {line.strip() for line in content.splitlines() if line.strip()}
        except (FileNotFoundError, OSError):
            return set()
