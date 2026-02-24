from typing import Protocol


class FileSystemManager(Protocol):
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

    def create_file(self, path: str, content: str) -> None:
        """
        Creates a new file with the given content.

        Raises:
            FileExistsError: If a file already exists at the specified path.
        """
        ...

    def read_file(self, path: str) -> str:
        """
        Reads the content of a file from the specified path.

        Raises:
            FileNotFoundError: If no file exists at the specified path.
        """
        ...

    def edit_file(self, path: str, find: str, replace: str) -> None:
        """
        Modifies an existing file by replacing a string.

        Raises:
            FileNotFoundError: If no file exists at the specified path.
        """
        ...

    def create_default_context_file(self) -> None:
        """
        Creates a default .teddy/project.context file with simplified content.
        """
        ...

    def get_context_paths(self) -> list[str]:
        """
        Reads all .teddy/*.context files and returns a deduplicated list of paths.
        """
        ...

    def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
        """
        Reads the content of multiple files. Returns content for found files
        and None for files that are not found.
        """
        ...
