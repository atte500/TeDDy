import logging
import os
from pathlib import Path
from typing import List, Sequence
from teddy_executor.core.ports.inbound.edit_simulator import EditPair, IEditSimulator
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager

# Configure debug logging
if os.environ.get("TEDDY_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

from teddy_executor.core.domain.models import (
    FileAlreadyExistsError,
)

logger = logging.getLogger(__name__)


class LocalFileSystemAdapter(FileSystemManager):
    """
    An adapter that implements file system operations on the local machine.
    """

    def __init__(self, edit_simulator: IEditSimulator, root_dir: str = "."):
        self._edit_simulator = edit_simulator
        self.root_dir = Path(root_dir)

    def _resolve_path(self, path: str) -> Path:
        """
        Resolves a path relative to the root_dir.
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj

        # Handle project-root-relative convention (e.g., '/file.txt')
        if path.startswith("/"):
            path = path[1:]

        return (self.root_dir.resolve() / path).resolve()

    def get_context_paths(self) -> list[str]:
        """
        Reads all .teddy/*.context files and returns a deduplicated list of paths.
        """
        teddy_dir = self.root_dir / ".teddy"
        if not teddy_dir.is_dir():
            return []

        context_files = [str(p) for p in teddy_dir.glob("*.context")]
        return self.resolve_paths_from_files(context_files)

    def resolve_paths_from_files(self, file_paths: Sequence[str]) -> list[str]:
        """
        Reads a list of context files and returns a deduplicated list of the paths they contain.
        """
        all_paths = set()
        for path in file_paths:
            content = self.read_file(path)
            for line in content.splitlines():
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    all_paths.add(stripped_line)

        return sorted(list(all_paths))

    def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
        """
        Reads the content of multiple files specified in a list.
        Returns content for found files and None for files that are not found.
        """
        contents: dict[str, str | None] = {}
        for path in paths:
            try:
                full_path = self.root_dir / path
                contents[path] = self.read_file(str(full_path))
            except FileNotFoundError:
                contents[path] = None  # Mark not found files with None
        return contents

    def path_exists(self, path: str) -> bool:
        """
        Checks if a path (file or directory) exists relative to the root_dir.
        """
        return self._resolve_path(path).exists()

    def create_directory(self, path: str) -> None:
        """
        Creates a directory, including any necessary parent directories.
        Does not raise an error if the directory already exists.
        """
        self._resolve_path(path).mkdir(parents=True, exist_ok=True)

    def write_file(self, path: str, content: str) -> None:
        """
        Writes content to a file, creating it if it doesn't exist
        and overwriting it if it does.
        """
        self._resolve_path(path).write_text(content, encoding="utf-8")

    def create_file(self, path: str, content: str) -> None:
        """
        Creates a new file with the given content using exclusive creation mode.
        """
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError as e:
            # Raise a domain-specific exception to conform to the port's contract.
            raise FileAlreadyExistsError(f"File exists: {path}", file_path=path) from e
        except IOError as e:
            # In a real-world scenario, we might want a more specific
            # domain exception here, but for now, this is sufficient.
            # For example, to handle permission errors.
            raise IOError(f"Failed to create file at {path}: {e}") from e

    def read_file(self, path: str) -> str:
        """
        Reads the content of a file from the specified path.
        """
        try:
            return self._resolve_path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            # Re-raise to conform to the port's contract
            raise
        except IOError as e:
            raise IOError(f"Failed to read file at {path}: {e}") from e

    def edit_file(
        self,
        path: str,
        edits: list[dict[str, str]],
    ) -> None:
        """
        Modifies an existing file by applying a list of find-and-replace blocks.
        """
        file_path = self._resolve_path(path)
        content = file_path.read_text(encoding="utf-8")

        # Cast to match the port's expected EditPair structure
        cast_edits: List[EditPair] = [
            {"find": e["find"], "replace": e["replace"]} for e in edits
        ]
        new_content = self._edit_simulator.simulate_edits(content, cast_edits)

        file_path.write_text(new_content, encoding="utf-8")
