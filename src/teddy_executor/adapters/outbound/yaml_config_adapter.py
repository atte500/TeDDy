import os
from typing import Any, Dict, Optional
import yaml
from teddy_executor.core.ports.outbound.config_service import IConfigService


class YamlConfigAdapter(IConfigService):
    """
    Implements IConfigService by reading configuration from a YAML file.
    """

    def __init__(
        self, config_path: str = ".teddy/config.yaml", root_dir: Optional[str] = None
    ):
        if root_dir:
            self._config_path = os.path.join(root_dir, config_path)
        else:
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
        Supports nested keys using dot notation (e.g., 'outer.inner').
        """
        if not key:
            return default

        # 1. Try exact match (handles flat keys or dotted keys in a flat dict)
        if key in self._config:
            return self._config[key]

        # 2. Try nested resolution (standard 'execution.similarity_threshold')
        parts = key.split(".")
        current = self._config
        found = True
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found:
            return current

        # 3. Try "doubled prefix" or path-based fallback
        # This handles 'execution.similarity_threshold' -> look for 'similarity_threshold'
        # Or 'execution.execution.key' -> look for 'execution.key'
        if len(parts) > 1:
            leaf_key = parts[-1]
            if leaf_key in self._config:
                return self._config[leaf_key]

            # Try one level deeper for doubled prefix
            second_attempt = ".".join(parts[1:])
            if second_attempt in self._config:
                return self._config[second_attempt]

        return default
