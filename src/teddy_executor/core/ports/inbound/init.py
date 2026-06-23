from abc import ABC, abstractmethod


class IInitUseCase(ABC):
    """
    Inbound port for project initialization.
    """

    @abstractmethod
    def ensure_initialized(self) -> str:
        """
        Ensures the .teddy/ directory and its essential configuration
        files are present in the current project root.

        Returns:
            A human-readable summary string (e.g., "Config: unchanged. Prompts: updated (3 files).").
        """
        pass

    @abstractmethod
    def ensure_prompts_initialized(self, overwrite: bool = False) -> str:
        """
        Ensures prompt XML files are present in the .teddy/prompts/ directory.

        Args:
            overwrite: If True, always overwrite existing prompt files with defaults.
                       If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Prompts overwritten (6 files).").
        """
        pass

    @abstractmethod
    def ensure_config_initialized(self, overwrite: bool = False) -> str:
        """
        Ensures configuration files (config.yaml, .gitignore, init.context) are present
        in the .teddy/ directory.

        Args:
            overwrite: If True, always overwrite existing config files with defaults.
                       If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Configuration files overwritten (3 files).").
        """
        pass
