from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager

DEFAULT_CONFIG_YAML = """# TeDDy Configuration

# LLM Settings
# llm:
#   model: "gemini/gemini-1.5-flash"
#   api_key: "your-api-key-here"
#   api_base: "https://generativelanguage.googleapis.com"
"""

DEFAULT_INIT_CONTEXT = """README.md
docs/ARCHITECTURE.md
"""


class InitService(IInitUseCase):
    """
    Service responsible for auto-initializing the .teddy directory.
    """

    def __init__(self, file_system: FileSystemManager):
        self._file_system = file_system

    def ensure_initialized(self) -> None:
        """
        Checks for and creates the .teddy directory and default files.
        """
        if not self._file_system.path_exists(".teddy"):
            self._file_system.create_directory(".teddy")

        gitignore_path = ".teddy/.gitignore"
        if not self._file_system.path_exists(gitignore_path):
            self._file_system.write_file(gitignore_path, "*")

        config_path = ".teddy/config.yaml"
        if not self._file_system.path_exists(config_path):
            self._file_system.write_file(config_path, DEFAULT_CONFIG_YAML)

        init_context_path = ".teddy/init.context"
        if not self._file_system.path_exists(init_context_path):
            self._file_system.write_file(init_context_path, DEFAULT_INIT_CONTEXT)
