import os
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


class InitService(IInitUseCase):
    """
    Service for initializing projects.
    """

    def __init__(self, file_system: IFileSystemManager, config_dir: str | None = None):
        self._file_system = file_system
        # Find the config directory relative to the package root if not provided
        self._config_dir = config_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "config"
        )

    def _get_default_content(self, filename: str) -> str | None:
        """Loads default content from the config directory."""
        path = os.path.join(self._config_dir, filename)
        if not os.path.exists(path):
            return None
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
            if content is not None:
                self._file_system.write_file(gitignore_path, content)

        config_path = ".teddy/config.yaml"
        if not self._file_system.path_exists(config_path):
            content = self._get_default_content("config.yaml")
            if content is not None:
                self._file_system.write_file(config_path, content)

        init_context_path = ".teddy/init.context"
        if not self._file_system.path_exists(init_context_path):
            content = self._get_default_content("init.context")
            if content is not None:
                self._file_system.write_file(init_context_path, content)
