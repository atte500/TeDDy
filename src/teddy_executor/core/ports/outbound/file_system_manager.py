from typing import Protocol, Sequence


class IFileSystemManager(Protocol):
    """
    An outbound port for interacting with a file system.
    """

    def path_exists(self, path: str) -> bool:
        """
        Checks if a path (file or directory) exists.
        """
        ...

    def create_directory(self, path: str) -> None:
        """
        Creates a directory, including any necessary parent directories.
        """
        ...

    def write_file(self, path: str, content: str) -> None:
        """
        Writes content to a file, creating it if it doesn't exist
        and overwriting it if it does.
        """
        ...

    def create_file(self, path: str, content: str, overwrite: bool = False) -> None:
        """
        Creates a new file with the given content.

        If overwrite is False (default), raises FileExistsError if the file already exists.
        If overwrite is True, replaces existing file content.

        Raises:
            FileExistsError: If a file already exists and overwrite is False.
        """
        ...

    def read_file(self, path: str) -> str:
        """
        Reads the content of a file from the specified path.

        Raises:
            FileNotFoundError: If no file exists at the specified path.
        """
        ...

    def edit_file(
        self,
        path: str,
        edits: list[dict[str, str]],
        similarity_threshold: float = 0.95,
        replace_all: bool = False,
    ) -> list[float]:
        """
        Modifies an existing file by applying a list of find-and-replace blocks.

        Raises:
            FileNotFoundError: If no file exists at the specified path.
        """
        ...

    def get_context_paths(self) -> list[str]:
        """
        Reads all .teddy/*.context files and returns a deduplicated list of paths.
        """
        ...

    def resolve_paths_from_files(self, file_paths: Sequence[str]) -> list[str]:
        """
        Reads a list of context files and returns a deduplicated list of the paths they contain.
        """
        ...

    def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
        """
        Reads the content of multiple files. Returns content for found files
        and None for files that are not found.
        """
        ...

    def list_directory(self, path: str) -> list[str]:
        """
        Lists the names of files and directories in the specified path.
        """
        ...

    def get_mtime(self, path: str) -> float:
        """
        Returns the modification time of a file or directory as a timestamp.
        """
        ...

    def move_directory(self, old_path: str, new_path: str) -> None:
        """
        Moves or renames a directory.
        """
        ...
