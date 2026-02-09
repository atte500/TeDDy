import logging
import os
from pathlib import Path
from typing import Optional
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager

# Configure debug logging
if os.environ.get("TEDDY_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

from teddy_executor.core.domain.models import (
    SearchTextNotFoundError,
    FileAlreadyExistsError,
    MultipleMatchesFoundError,
)

logger = logging.getLogger(__name__)


class LocalFileSystemAdapter(FileSystemManager):
    """
    An adapter that implements file system operations on the local machine.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)

    def _resolve_path(self, path: str) -> Path:
        """
        Resolves a path relative to the root_dir.
        Handles project-root-relative paths (e.g., '/file.txt') by stripping the
        leading slash before joining with the root directory.
        """
        logger.debug("--- Resolving Path ---")
        logger.debug(f"Input path: '{path}'")
        logger.debug(f"Adapter root_dir: '{self.root_dir}'")

        path_obj = Path(path)

        # First, check if the original path is absolute. If so, use it directly.
        # This correctly handles paths from pytest's tmp_path fixture on Unix.
        if path_obj.is_absolute():
            logger.debug(f"Path is absolute, returning directly: '{path_obj}'")
            return path_obj

        # Handle the project-root-relative convention (e.g., '/file.txt').
        # This is now safe because we've already handled true absolute paths.
        if path.startswith("/"):
            path = path[1:]
            logger.debug(f"Path after stripping '/': '{path}'")

        resolved_root = self.root_dir.resolve()
        logger.debug(f"Resolved adapter root_dir: '{resolved_root}'")

        final_path = resolved_root / path
        logger.debug(f"Final resolved path: '{final_path}'")
        logger.debug("----------------------")
        return final_path

    def create_default_context_file(self) -> None:
        """
        Creates a default .teddy/perm.context file with simplified content
        and a .gitignore to ignore the directory's contents.
        """
        teddy_dir = self.root_dir / ".teddy"
        teddy_dir.mkdir(exist_ok=True)

        # Create .gitignore
        gitignore_file = teddy_dir / ".gitignore"
        gitignore_file.write_text("*", encoding="utf-8")

        # Create perm.context
        perm_context_file = teddy_dir / "perm.context"
        default_content = "README.md\ndocs/ARCHITECTURE.md\n"
        perm_context_file.write_text(default_content, encoding="utf-8")

    def get_context_paths(self) -> list[str]:
        """
        Reads all .teddy/*.context files and returns a deduplicated list of paths.
        """
        teddy_dir = self.root_dir / ".teddy"
        if not teddy_dir.is_dir():
            return []

        all_paths = set()
        context_files = list(teddy_dir.glob("*.context"))

        for context_file in context_files:
            content = context_file.read_text(encoding="utf-8")
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

    def _check_matches_and_raise(
        self, num_matches: int, find_str_repr: str, content: str
    ):
        """Checks match count and raises domain exceptions for ambiguity or not found."""
        if num_matches > 1:
            raise MultipleMatchesFoundError(
                message=f"Found {num_matches} occurrences of '{find_str_repr}'. Aborting edit to prevent ambiguity.",
                content=content,
            )
        if num_matches == 0:
            raise SearchTextNotFoundError(
                message=f"Search text '{find_str_repr}' not found in file.",
                content=content,
            )

    def _apply_single_edit(self, content: str, find: str, replace: str) -> str:
        """
        Applies a single find/replace operation to content.

        This is a simple, verbatim replacement. The AI is responsible for
        providing an exact `find` block and a correctly indented `replace` block.
        """
        # An empty find string would result in len(content) + 1 matches,
        # which would correctly raise MultipleMatchesFoundError. No special handling needed.
        num_matches = content.count(find)

        # Use repr() to make whitespace visible in error messages.
        self._check_matches_and_raise(num_matches, repr(find), content)

        return content.replace(find, replace, 1)

    def edit_file(
        self,
        path: str,
        find: Optional[str] = None,
        replace: Optional[str] = None,
        edits: Optional[list[dict[str, str]]] = None,
    ) -> None:
        """
        Modifies an existing file by replacing block(s) of text.
        Supports either a single find/replace pair or a list of edits.
        """
        file_path = self._resolve_path(path)
        content = file_path.read_text(encoding="utf-8")

        if edits:
            for edit in edits:
                content = self._apply_single_edit(
                    content, edit["find"], edit["replace"]
                )
        elif find is not None and replace is not None:
            content = self._apply_single_edit(content, find, replace)
        else:
            raise ValueError(
                "Either 'edits' list or 'find'/'replace' pair must be provided."
            )

        file_path.write_text(content, encoding="utf-8")
