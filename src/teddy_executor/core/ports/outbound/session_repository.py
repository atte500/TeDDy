from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Protocol, Set


class ISessionRepository(Protocol):
    """
    Outbound port for session persistence, path resolution, and metadata management.
    """

    def get_latest_session_name(self) -> str:
        """Identifies and returns the name of the latest session."""
        ...

    def resolve_session_from_path(self, path: str) -> str:
        """Resolves a session name from a given filesystem path."""
        ...

    def is_valid_path(self, path_str: str) -> bool:
        """Checks if a string is a plausible file path."""
        ...

    def read_context_file(self, path: str) -> Set[str]:
        """Reads and parses a context file (session or turn)."""
        ...

    def to_root_relative(self, turn_dir: Path, filename: str) -> str:
        """Calculates a root-relative path for a file within a turn directory."""
        ...

    def load_meta(self, turn_dir: str) -> Dict[str, Any]:
        """Loads and parses metadata for a specific turn."""
        ...

    def save_meta(self, path: str, data: Dict[str, Any]) -> None:
        """Serializes and persists metadata to the filesystem."""
        ...

    def copy_prompt(self, src_dir: str, dest_dir: str, agent: str) -> None:
        """Copies an agent prompt file between turn directories."""
        ...

    def get_latest_turn(self, session_name: str) -> str:
        """Identifies and returns the path to the latest turn in a session."""
        ...

    def rename_session(self, old_name: str, new_name: str) -> str:
        """Renames a session directory on the filesystem."""
        ...

    def resolve_context_paths(self, plan_path: str) -> Dict[str, list[str]]:
        """Locates and returns the contents of session and turn context files."""
        ...

    def create_turn_directory(self, turn_dir: str) -> None:
        """Ensures a turn directory exists."""
        ...

    def path_exists(self, path: str) -> bool:
        """Checks if a path exists on the filesystem."""
        ...

    def list_directory(self, path: str) -> list[str]:
        """Lists the contents of a directory."""
        ...
