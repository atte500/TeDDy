import os
from typing import Any, Dict, Optional
import yaml
from teddy_executor.core.ports.outbound.config_service import IConfigService


class YamlConfigAdapter(IConfigService):
    """
    Implements IConfigService by reading configuration from a YAML file.
    """

    def __init__(self, config_path: str = ".teddy/config.yaml"):
        self._config_path = config_path
        self._config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads the YAML configuration file if it exists."""
        if not os.path.exists(self._config_path):
            return {}

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, OSError):
            return {}

    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Retrieves a configuration value by its key from the loaded YAML.
        """
        if not key:
            return default

        return self._config.get(key, default)
