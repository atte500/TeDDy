from pathlib import Path
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.domain.models import (
    SearchTextNotFoundError,
    FileAlreadyExistsError,
    MultipleMatchesFoundError,
)


class LocalFileSystemAdapter(FileSystemManager):
    """
    An adapter that implements file system operations on the local machine.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)

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
        return (self.root_dir / path).exists()

    def create_directory(self, path: str) -> None:
        """
        Creates a directory, including any necessary parent directories.
        Does not raise an error if the directory already exists.
        """
        Path(path).mkdir(parents=True, exist_ok=True)

    def write_file(self, path: str, content: str) -> None:
        """
        Writes content to a file, creating it if it doesn't exist
        and overwriting it if it does.
        """
        Path(path).write_text(content, encoding="utf-8")

    def create_file(self, path: str, content: str) -> None:
        """
        Creates a new file with the given content using exclusive creation mode.
        """
        try:
            # FIX: Ensure the parent directory exists before writing the file.
            file_path = Path(path)
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
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            # Re-raise to conform to the port's contract
            raise
        except IOError as e:
            raise IOError(f"Failed to read file at {path}: {e}") from e

    def _normalize_lines_by_common_indent(self, lines: list[str]) -> list[str]:
        """
        Removes the common leading whitespace from a list of strings.
        Preserves relative indentation.
        """
        non_empty_lines = [line for line in lines if line.strip()]
        if not non_empty_lines:
            return lines

        min_indent = min(len(line) - len(line.lstrip(" ")) for line in non_empty_lines)

        return [line[min_indent:] for line in lines]

    def _find_multiline_match_indices(
        self, source_lines: list[str], find_lines: list[str]
    ) -> list[int]:
        """
        Finds the starting indices of all multiline matches, ignoring absolute
        indentation but respecting relative indentation.
        """
        if not find_lines:
            return []

        normalized_find_lines = self._normalize_lines_by_common_indent(find_lines)

        match_indices = []
        for i in range(len(source_lines) - len(normalized_find_lines) + 1):
            source_slice = source_lines[i : i + len(normalized_find_lines)]
            normalized_source_slice = self._normalize_lines_by_common_indent(
                source_slice
            )

            if normalized_source_slice == normalized_find_lines:
                match_indices.append(i)

        return match_indices

    def _reconstruct_content(
        self,
        original_content: str,
        source_lines: list[str],
        find_lines: list[str],
        replace_lines: list[str],
        match_start_index: int,
    ) -> str:
        """Reconstructs the file content with the replacement."""
        pre_match_lines = source_lines[:match_start_index]
        post_match_lines = source_lines[match_start_index + len(find_lines) :]

        final_lines = pre_match_lines + replace_lines + post_match_lines
        new_content = "\n".join(final_lines)

        # Preserve a single trailing newline if the original had one
        if original_content.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"

        return new_content

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

    def edit_file(self, path: str, find: str, replace: str) -> None:
        """
        Modifies an existing file by replacing a block of text, handling
        indentation for multiline blocks. Fails if the `find` block is
        ambiguous (multiple occurrences) or not found.
        """
        file_path = Path(path)

        if not find:  # If find is empty, replace the entire file content.
            file_path.write_text(replace, encoding="utf-8")
            return

        original_content = file_path.read_text(encoding="utf-8")

        # Use different strategies for single-line and multi-line `find` blocks.
        if "\n" not in find:
            # For single-line, use robust substring counting.
            num_matches = original_content.count(find)
            self._check_matches_and_raise(num_matches, find, original_content)
            # The check above ensures there's exactly one match, so a global replace is safe.
            new_content = original_content.replace(find, replace)
            file_path.write_text(new_content, encoding="utf-8")
        else:
            # For multi-line, use line-based matching for indentation handling.
            source_lines = original_content.splitlines()
            # CORRECT FIX: Do not strip the find block, as it can contain meaningful newlines.
            find_lines = find.splitlines()

            if not find.strip():  # Handle case where find is just whitespace
                file_path.write_text(replace, encoding="utf-8")
                return

            match_indices = self._find_multiline_match_indices(source_lines, find_lines)
            num_matches = len(match_indices)
            self._check_matches_and_raise(
                num_matches, "multi-line block", original_content
            )

            # Perform the replacement
            match_start_index = match_indices[0]
            replace_lines = replace.splitlines()
            new_content = self._reconstruct_content(
                original_content,
                source_lines,
                find_lines,
                replace_lines,
                match_start_index,
            )
            file_path.write_text(new_content, encoding="utf-8")
