from teddy.core.ports.outbound.file_system_manager import FileSystemManager


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
        except FileExistsError:
            # Re-raise to conform to the port's contract.
            raise
        except IOError as e:
            # In a real-world scenario, we might want a more specific
            # domain exception here, but for now, this is sufficient.
            # For example, to handle permission errors.
            raise IOError(f"Failed to create file at {path}: {e}") from e
