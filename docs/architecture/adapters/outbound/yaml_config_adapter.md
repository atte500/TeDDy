**Status:** Refactoring

## 1. Purpose / Responsibility

The `YamlConfigAdapter` is responsible for reading and writing application configuration from/to a YAML file (`.teddy/config.yaml`). It provides a concrete implementation for the `IConfigService` port, supporting both retrieval and persistence of configuration settings.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `IConfigService`

## 3. Implementation Details / Logic

### Reading
-   **Layered Loading:** The adapter loads configuration in two layers: baseline (bundled `config.yaml` via `importlib.resources`) and user overrides (`.teddy/config.yaml`). The user config is deep-merged over the baseline.
-   **Caching:** On first load, the full merged config is cached in `self._config` to avoid redundant file I/O.
-   **Nested Key Support:** Supports dot-notation for retrieving nested keys (e.g., `execution.default_timeout_seconds`). Exact top-level keys take priority over nested resolution.
-   **Missing Config File:** If the user config file does not exist, only baseline values are used. Returns `default` or `None` for missing keys.

### Writing (`set_setting`)
-   **Read-Modify-Write:** Reads the current user config file, merges the new value, and writes it back via `yaml.dump()`.
-   **File Creation:** If the config file does not exist, it is created automatically (including parent directories as needed).
-   **Cache Synchronization:** After writing, the in-memory `_config` cache is updated immediately so subsequent `get_setting()` calls reflect the change without reloading.
-   **Dot-Notation Traversal:** Supports nested key setting via dot-notation (e.g., `llm.model`), creating intermediate dicts as needed.
-   **Limitations:** `yaml.dump()` strips YAML comments from the user config file. Comments are only present in the baseline bundled config, which is never written to by `set_setting()`.

## 4. Data Contracts / Methods

### `get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]`
-   **Preconditions:** Key must be a non-empty string.
-   **Postconditions:** Returns the value for the given key, or the default value if not found. Returns `None` if no default is provided and key is missing.
-   **Exceptions:** None (returns default or None on failure).

### `set_setting(self, key: str, value: Any) -> None`
-   **Preconditions:** Key must be a non-empty string. Value may be any YAML-serializable type.
-   **Postconditions:** The value is persisted to the user config file. The in-memory cache is updated immediately.
-   **Exceptions:** May raise `OSError` if the config file cannot be written. May raise `yaml.YAMLError` if serialization fails.
-   **Invariants:** After `set_setting()`, `get_setting(key)` returns the new value. Other keys in the config are preserved unchanged.

### `get_config_path() -> str`
-   **Preconditions:** None.
-   **Postconditions:** Returns the absolute or relative path to the user config file.
-   **Exceptions:** None.
