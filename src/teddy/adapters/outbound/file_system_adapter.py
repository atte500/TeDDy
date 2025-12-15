from pathlib import Path
from teddy.core.ports.outbound.file_system_manager import FileSystemManager
from teddy.core.domain.models import SearchTextNotFoundError, FileAlreadyExistsError


class LocalFileSystemAdapter(FileSystemManager):
    """
    An adapter that implements file system operations on the local machine.
    """

    def create_file(self, path: str, content: str) -> None:
        """
        Creates a new file with the given content using exclusive creation mode.
        """
        try:
            with open(path, "x", encoding="utf-8") as f:
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

    def _find_multiline_match_index(
        self, source_lines: list[str], find_lines: list[str]
    ) -> int:
        """Finds the starting index of a multiline match."""
        normalized_find_lines = [line.strip() for line in find_lines]
        if not normalized_find_lines:
            return -1

        for i in range(len(source_lines) - len(normalized_find_lines) + 1):
            is_match = True
            for j in range(len(normalized_find_lines)):
                if source_lines[i + j].strip() != normalized_find_lines[j]:
                    is_match = False
                    break
            if is_match:
                return i
        return -1

    def _reconstruct_content(
        self,
        original_content: str,
        source_lines: list[str],
        find_lines: list[str],
        replace_lines: list[str],
        match_start_index: int,
    ) -> str:
        """Reconstructs the file content with the replacement."""
        first_match_line = source_lines[match_start_index]
        indentation = first_match_line[
            : len(first_match_line) - len(first_match_line.lstrip())
        ]

        indented_replace_lines = [indentation + line for line in replace_lines]

        pre_match_lines = source_lines[:match_start_index]
        post_match_lines = source_lines[match_start_index + len(find_lines) :]

        final_lines = pre_match_lines + indented_replace_lines + post_match_lines
        new_content = "\n".join(final_lines)

        # Preserve a single trailing newline if the original had one
        if original_content.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"

        return new_content

    def edit_file(self, path: str, find: str, replace: str) -> None:
        """
        Modifies an existing file by replacing a block of text, handling
        indentation for multiline blocks.
        """
        file_path = Path(path)

        # If find is empty, replace the entire file content.
        if not find:
            file_path.write_text(replace, encoding="utf-8")
            return

        original_content = file_path.read_text(encoding="utf-8")

        # For single-line finds, a simple substring check and replace is robust.
        if "\n" not in find:
            if find in original_content:
                new_content = original_content.replace(find, replace)
                file_path.write_text(new_content, encoding="utf-8")
                return
            else:
                raise SearchTextNotFoundError(
                    message="Search text was not found in the file.",
                    content=original_content,
                )

        # For multiline finds, we must use the line-based matching logic.
        source_lines = original_content.splitlines()
        find_lines = find.strip().splitlines()

        if not find_lines:  # Handle case where find is just whitespace
            file_path.write_text(replace, encoding="utf-8")
            return

        match_start_index = self._find_multiline_match_index(source_lines, find_lines)

        if match_start_index != -1:
            replace_lines = replace.strip().splitlines()
            new_content = self._reconstruct_content(
                original_content,
                source_lines,
                find_lines,
                replace_lines,
                match_start_index,
            )
            file_path.write_text(new_content, encoding="utf-8")
        else:
            # If the multiline match fails, the text is considered not found.
            raise SearchTextNotFoundError(
                message="Search text was not found in the file.",
                content=original_content,
            )
