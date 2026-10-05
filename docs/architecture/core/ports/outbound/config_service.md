**Status:** Implemented

## 1. Purpose / Responsibility

The `IConfigService` port defines a technology-agnostic interface for retrieving and persisting application configuration, including settings and secrets like API keys. It abstracts the underlying storage mechanism (e.g., YAML file, environment variables) from the core application logic.

## 2. Ports

-   **Type:** Outbound Port
-   **Used by:** Any core service or adapter that requires access to configuration (e.g., `ILlmClient`).
-   **Implemented by:** Adapters like `YamlConfigAdapter`.

## 3. Implementation Details / Logic

This is an interface and contains no implementation logic.

## 4. Data Contracts / Methods

### `get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]`

-   **Description:** Retrieves a configuration value by its key.
-   **Preconditions:**
    -   `key` must be a non-empty string.
-   **Postconditions:**
    -   If the key exists, its corresponding value is returned.
    -   If the key does not exist and a `default` is provided, the `default` value is returned.
    -   If the key does not exist and no `default` is provided, `None` is returned.
-   **Exception/Error States:** None. The contract guarantees a return value.

### `set_setting(self, key: str, value: Any) -> None`

-   **Description:** Sets a configuration value by its key and persists to the underlying storage (e.g., YAML file). Supports dot-notation for nested keys.
-   **Preconditions:**
    -   `key` must be a non-empty string.
-   **Postconditions:**
    -   The value for the given key is updated and persisted.
    -   The in-memory cache is updated to reflect the change immediately.
-   **Exception/Error States:**
    -   May raise `OSError` if the config file cannot be written (e.g., insufficient permissions).
    -   May raise `yaml.YAMLError` if the config file becomes corrupted during write.

### `set_env_variable(self, name: str, value: str) -> None`

-   **Description:** Persists a secret to the `.env` file inside the config directory (the storage layer that backs `${VAR}` interpolation). Mirrors the `set_setting` persistence contract, but for secrets.
-   **Preconditions:**
    -   `name` must be a non-empty environment-variable name.
    -   `value` may be any string secret.
-   **Postconditions:**
    -   The value is persisted to the `.env` file inside the config directory (created if missing).
    -   `os.environ` is NOT mutated.
-   **Exception/Error States:**
    -   May raise `OSError` if the `.env` file cannot be written (e.g., insufficient permissions).
-   **Invariants:** The secret is written to disk only; the process environment is left untouched, so later child processes never inherit the secret.

## 5. Standard Configuration Keys

- `yolo_default`: Boolean setting the default mode for the `--yolo` / `-y` flag across `start`, `resume`, and `execute` (default `False`). When `true`, sessions run non-interactively unless overridden by `--no-yolo` / `-n`; the code-level default keeps pre-existing configs unchanged.
- `execution.similarity_threshold`: Float value for fuzzy matching.
- `max_execute_lines`: Integer limit for `EXECUTE` output truncation (default 100).
- `max_read_lines`: Integer limit for `READ` output truncation (default 1000).
- `auto_pruning.enabled`: Boolean toggling the entire auto-pruning heuristic system.
- `auto_pruning.turn_context_threshold`: Integer token budget for Turn-scope files only (excludes session.context and system prompts).
- `auto_pruning.prune_preceding_on_non_green`: Boolean toggling the pruning of turns preceding a 🔴/🟡 state.
- `auto_pruning.prune_validation_failures`: Boolean toggling the pruning of failed validation reports and their plans.
