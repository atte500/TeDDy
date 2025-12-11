from typing import Protocol


class FileSystemManager(Protocol):
    """
    An outbound port for interacting with a file system.
    """

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
