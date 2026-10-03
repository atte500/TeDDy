from abc import ABC, abstractmethod
from typing import Any, Optional


class IConfigService(ABC):
    """
    Interface for retrieving application configuration and secrets.
    """

    @abstractmethod
    def get_config_path(self) -> str:
        """
        Returns the absolute or relative path to the configuration file.
        """
        pass

    @abstractmethod
    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Retrieves a configuration value by its key.

        Args:
            key: The configuration key to retrieve.
            default: The default value to return if the key is not found.

        Returns:
            The configuration value, or the default value if not found.
        """
        pass

    @abstractmethod
    def set_setting(self, key: str, value: Any) -> None:
        """
        Sets a configuration value and persists it to the underlying storage.
        Supports dot-notation for nested keys.

        Args:
            key: The configuration key to set.
            value: The value to persist.
        """
        pass
