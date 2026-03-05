import os
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager


class InitService(IInitUseCase):
    """
    Service responsible for auto-initializing the .teddy directory.
    """

    def __init__(self, file_system: FileSystemManager):
        self._file_system = file_system
        # Find the config directory relative to the package root
        self._config_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "config"
        )

    def _get_default_content(self, filename: str) -> str:
        """Loads default content from the config directory."""
        path = os.path.join(self._config_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def ensure_initialized(self) -> None:
        """
        Checks for and creates the .teddy directory and default files.
        """
        if not self._file_system.path_exists(".teddy"):
            self._file_system.create_directory(".teddy")

        gitignore_path = ".teddy/.gitignore"
        if not self._file_system.path_exists(gitignore_path):
            content = self._get_default_content(".gitignore")
            self._file_system.write_file(gitignore_path, content)

        config_path = ".teddy/config.yaml"
        if not self._file_system.path_exists(config_path):
            content = self._get_default_content("config.yaml")
            self._file_system.write_file(config_path, content)

        init_context_path = ".teddy/init.context"
        if not self._file_system.path_exists(init_context_path):
            content = self._get_default_content("init.context")
            self._file_system.write_file(init_context_path, content)
