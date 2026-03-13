from typing import Protocol, List, Optional


class ISystemEnvironment(Protocol):
    def which(self, command: str) -> Optional[str]:
        """Wraps shutil.which."""
        ...

    def get_env(self, key: str) -> Optional[str]:
        """Wraps os.getenv."""
        ...

    def run_command(
        self, args: List[str], check: bool = True, background: bool = False
    ) -> None:
        """Wraps subprocess.run (synchronous) or subprocess.Popen (background)."""
        ...

    def create_temp_file(self, suffix: str = "", mode: str = "w") -> str:
        """Creates a temporary file and returns its path."""
        ...

    def delete_file(self, path: str) -> None:
        """Wraps os.unlink."""
        ...
