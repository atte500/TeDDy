from abc import ABC, abstractmethod

from teddy_executor.core.domain.models.drift_report import DriftReport


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
            A human-readable summary string (e.g., "Config: unchanged.
            Prompts: updated (6 files). Templates: updated (11 files).").
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
        Ensures configuration files (config.yaml, .gitignore, init.context, .env) are present
        in the .teddy/ directory.

        Args:
            overwrite: If True, always overwrite existing config files with defaults.
                       If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Configuration files overwritten (4 files).").
        """
        pass

    @abstractmethod
    def ensure_templates_initialized(self, overwrite: bool = False) -> str:
        """
        Ensures Markdown templates are present in the docs/templates/ directory.

        Args:
            overwrite: If True, always overwrite existing template files with defaults.
                       If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Templates updated (11 files).").
        """
        pass

    @abstractmethod
    def check_drift(self) -> DriftReport:
        """
        Compares the user's prompts and templates against the bundled defaults.

        Returns:
            A DriftReport enumerating which ``.teddy/prompts/*.xml`` and
            ``docs/templates/*.md`` files are edited or missing relative to the
            bundled defaults.
        """
        pass
