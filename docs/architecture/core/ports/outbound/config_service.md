**Status:** Refactoring

## 1. Purpose / Responsibility

The `IConfigService` port defines a technology-agnostic interface for retrieving application configuration, including settings and secrets like API keys. It abstracts the underlying storage mechanism (e.g., YAML file, environment variables) from the core application logic.

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

## 5. Standard Configuration Keys

- `execution.similarity_threshold`: Float value for fuzzy matching.
- `max_execute_lines`: Integer limit for `EXECUTE` output truncation (default 100).
- `max_read_lines`: Integer limit for `READ` output truncation (default 1000).
- `auto_pruning.enabled`: Boolean toggling the entire auto-pruning heuristic system.
- `auto_pruning.global_context_threshold`: Integer total token limit for turn context.
- `auto_pruning.prune_preceding_on_non_green`: Boolean toggling the pruning of turns preceding a 🔴/🟡 state.
- `auto_pruning.prune_validation_failures`: Boolean toggling the pruning of failed validation reports and their plans.
