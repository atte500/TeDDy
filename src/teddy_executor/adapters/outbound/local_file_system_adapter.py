import logging
import os
from pathlib import Path
from typing import List, Sequence
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.ports.inbound.edit_simulator import EditPair, IEditSimulator
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.utils.string import truncate_lines

# Configure debug logging
if os.environ.get("TEDDY_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

from teddy_executor.core.domain.models import (
    FileAlreadyExistsError,
)

logger = logging.getLogger(__name__)


class LocalFileSystemAdapter(IFileSystemManager):
    """
    An adapter that implements file system operations on the local machine.
    """

    def __init__(
        self,
        edit_simulator: IEditSimulator,
        root_dir: str = ".",
        max_read_lines: int = 1000,
    ):
        self._edit_simulator = edit_simulator
        self.root_dir = Path(root_dir)
        self.max_read_lines = max_read_lines

    def _resolve_path(self, path: str) -> Path:
        """
        Resolves a path relative to the root_dir.
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            # Optimization: Only resolve if there are symlinks or ".." components.
            if ".." in str(path) or path_obj.is_symlink():
                return path_obj.resolve()
            return path_obj

        # Systemic Fix: Strictly follow project-root-relative convention.
        # We strip leading slashes and Windows drive letters to ensure the path
        # is always joined with our controlled root_dir.
        clean_path = str(path).replace("\\", "/")

        # Remove drive letter (e.g., C:) if present
        if ":" in clean_path and clean_path[1] == ":":
            clean_path = clean_path[2:]

        clean_path = clean_path.lstrip("/")

        # Join and resolve. This ensures we have a canonical, absolute path
        # within our root_dir, preventing macOS resolution hangs.
        # Optimization: Pre-resolve root_dir once (though here we rely on Path caching).
        base = self.root_dir.resolve()
        target = base / clean_path

        # Only resolve if strictly necessary to avoid performance hits in loops
        if ".." in clean_path or target.is_symlink():
            return target.resolve()
        return target

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
            try:
                content = self.read_file(path)
                for line in content.splitlines():
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith("#"):
                        # Skip strings with illegal filename characters on Windows/Unix
                        if any(c in stripped_line for c in '*?"<>|'):
                            continue
                        all_paths.add(stripped_line)
            except (FileNotFoundError, OSError, ValueError):
                continue

        return sorted(list(all_paths))

    def list_directory(self, path: str) -> list[str]:
        """
        Lists the names of files and directories in the specified path.
        """
        dir_path = self._resolve_path(path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")
        return [p.name for p in dir_path.iterdir()]

    def get_mtime(self, path: str) -> float:
        """
        Returns the modification time of a file or directory as a timestamp.
        """
        target = self._resolve_path(path)
        return target.stat().st_mtime

    def move_directory(self, old_path: str, new_path: str) -> None:
        """
        Moves or renames a directory.
        """
        import shutil

        source = self._resolve_path(old_path)
        destination = self._resolve_path(new_path)

        if not source.exists():
            raise FileNotFoundError(f"Source directory not found: {old_path}")
        if destination.exists():
            raise FileExistsError(f"Destination directory already exists: {new_path}")

        shutil.move(str(source), str(destination))

    def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
        """
        Reads the content of multiple files specified in a list.
        Returns content for found files and None for files that are not found.
        """
        contents: dict[str, str | None] = {}
        for path in paths:
            try:
                # read_file already calls _resolve_path, which joins with root_dir.
                contents[path] = self.read_file(path)
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

    def create_file(self, path: str, content: str, overwrite: bool = False) -> None:
        """
        Creates a new file with the given content.
        """
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "w" if overwrite else "x"
            with open(file_path, mode, encoding="utf-8") as f:
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
            content = self._resolve_path(path).read_text(encoding="utf-8")
            return truncate_lines(
                content,
                max_lines=self.max_read_lines,
                direction="head",
                action_type="read",
            )
        except FileNotFoundError:
            # Re-raise to conform to the port's contract
            raise
        except IOError as e:
            raise IOError(f"Failed to read file at {path}: {e}") from e

    def edit_file(
        self,
        path: str,
        edits: list[dict[str, str]],
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        match_all: bool = False,
    ) -> list[float]:
        """
        Modifies an existing file by applying a list of find-and-replace blocks.
        """
        file_path = self._resolve_path(path)
        content = file_path.read_text(encoding="utf-8")

        # Cast to match the port's expected EditPair structure
        cast_edits: List[EditPair] = []
        for e in edits:
            pair: EditPair = {"find": e["find"], "replace": e["replace"]}
            cast_edits.append(pair)

        new_content, scores = self._edit_simulator.simulate_edits(
            content,
            cast_edits,
            threshold=similarity_threshold,
            match_all=match_all,
        )

        file_path.write_text(new_content, encoding="utf-8")
        return scores
