**Status:** Implemented

## 1. Purpose / Responsibility

The `YamlConfigAdapter` is responsible for reading and writing application configuration from/to a YAML file (`.teddy/config.yaml`). It provides a concrete implementation for the `IConfigService` port, supporting retrieval (with lazy `${VAR}` interpolation), persistence of settings, and persistence of secrets to a sibling `.teddy/.env` file.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `IConfigService`

## 3. Implementation Details / Logic

### Reading
-   **Layered Loading:** The adapter loads configuration in two layers: baseline (bundled `config.yaml` via `importlib.resources`) and user overrides (`.teddy/config.yaml`). The user config is deep-merged over the baseline.
-   **Caching:** On first load, the full merged config is cached in `self._config` to avoid redundant file I/O.
-   **Nested Key Support:** Supports dot-notation for retrieving nested keys (e.g., `execution.default_timeout_seconds`). Exact top-level keys take priority over nested resolution.
-   **Missing Config File:** If the user config file does not exist, only baseline values are used. Returns `default` or `None` for missing keys.
-   **`${VAR}` Interpolation (value-only, lazy):** When a retrieved value is a string containing a `${...}` token, it is interpolated at `get_setting` time (in BOTH the exact-match and nested-resolution paths) — never at load time. Supported forms:
    - `${VAR}` — substituted with the variable's value, or the empty string when the variable is unresolved.
    - `${VAR:-default}` — substitutes `default` when the variable is unresolved.
    - `$$` — an escaped literal `$` (consumes the escape so the trailing text is not re-interpolated).
    Values with no `${` token are returned verbatim, and non-string values (numbers, mappings) are never interpolated.
-   **Env Layering & Fresh `.env` Read:** The interpolation lookup table layers `dotenv_values('.teddy/.env')` UNDER `os.environ`, so a real shell environment variable wins over the `.env` file. `.teddy/.env` is read FRESH on every interpolating call (never cached), which keeps a key persisted mid-run live across the transient `IConfigService` instances (`punq.Scope.transient`) with no explicit refresh call.

### Writing (`set_setting`)
-   **Surgical Edit (comment-preserving):** The user config is rewritten as raw text so that ONLY the target key's value token changes; comments, key ordering, blank lines and inline comments are preserved. The adapter does NOT round-trip the document through `yaml.dump()`.
-   **File Creation:** If the config file does not exist, it is created automatically (including parent directories as needed).
-   **Cache Synchronization:** After writing, the in-memory `_config` cache is updated immediately so subsequent `get_setting()` calls reflect the change without reloading.
-   **Dot-Notation Traversal:** Supports nested key setting via dot-notation (e.g., `llm.model`), creating intermediate mappings as needed.

### Writing Secrets (`set_env_variable`)
-   **`.env` Persistence:** Persists a secret to `.teddy/.env` via `dotenv.set_key(..., quote_mode="always")`, creating the parent directory as needed. The secret is written to the file ONLY.
-   **No `os.environ` Mutation:** `os.environ` is never mutated (the adapter uses `dotenv_values`/`set_key`, never `load_dotenv`), so a persisted key cannot leak into the child shells that `EXECUTE` actions spawn inside the user's repo.

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

### `set_env_variable(self, name: str, value: str) -> None`
-   **Preconditions:** `name` must be a non-empty environment-variable name; `value` may be any string secret.
-   **Postconditions:** The value is persisted to the `.env` file inside the config directory (created if missing). `os.environ` is NOT mutated.
-   **Exceptions:** May raise `OSError` if the `.env` file cannot be written.
-   **Invariants:** The secret is written to disk only; the process environment is left untouched, so later `EXECUTE` child shells never inherit it.
