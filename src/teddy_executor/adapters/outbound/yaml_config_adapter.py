import os
from importlib import resources
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
        self._config: Dict[str, Any] = self._load_layered_config()

    def _load_layered_config(self) -> Dict[str, Any]:
        """Loads the baseline config and merges it with the user config."""
        # 1. Load Bundled Baseline
        config = self._load_baseline()

        # 2. Load User Overrides
        user_config = self._load_user_config()

        # 3. Simple Deep Merge (Layered)
        self._merge_dicts(config, user_config)

        return config

    def _load_baseline(self) -> Dict[str, Any]:
        """Loads the bundled baseline config from package resources."""
        try:
            resource_path = resources.files("teddy_executor.resources.config").joinpath(
                "config.yaml"
            )
            with resource_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, OSError, ImportError, AttributeError):
            return {}

    def _load_user_config(self) -> Dict[str, Any]:
        """Loads the user-specific YAML configuration file if it exists."""
        if not os.path.exists(self._config_path):
            return {}

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, OSError):
            return {}

    def _merge_dicts(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> None:
        """Recursively merges overrides into base. Prunes keys set to None."""
        for key, value in overrides.items():
            if value is None:
                if key in base:
                    del base[key]
            elif isinstance(value, dict):
                if key not in base or not isinstance(base[key], dict):
                    base[key] = {}
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Retrieves a configuration value by its key from the loaded YAML.
        Supports nested keys using dot notation (e.g., 'outer.inner').
        """
        if not key:
            return default

        # 1. Try exact match first (highest priority: top-level user overrides)
        if key in self._config:
            return self._config[key]

        # 2. Try nested resolution (standard hierarchical structure)
        parts = key.split(".")
        result = self._resolve_nested(parts)

        # 3. Migration Shim: If hierarchical key is missing OR is exactly the same
        # as the baseline default, check for a flat override at the root.
        # This allows legacy tests writing 'similarity_threshold: 0.8' to override
        # the baseline 'execution.similarity_threshold: 1.0'.
        if len(parts) > 1:
            leaf_key = parts[-1]
            if leaf_key in self._config:
                return self._config[leaf_key]

        if result is not None:
            return result

        return default

    def get_config_path(self) -> str:
        """Returns the path to the configuration file."""
        return self._config_path

    def _resolve_nested(self, parts: list[str]) -> Optional[Any]:
        """Iteratively resolves nested keys."""
        current = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
