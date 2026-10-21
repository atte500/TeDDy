# Component Design: IConfigService
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/config_service.py`](/src/teddy_executor/core/ports/outbound/config_service.py)

## Purpose
Defines the outbound port for retrieving and persisting application configuration and secrets. It hides the storage layer (a YAML file plus a `.env` file) from the core so services read settings without knowing the backing format.

## Consumers
- [`LiteLLMAdapter`](../../../adapters/outbound/litellm_adapter.md): Reads `llm.*` settings and the API key.
- [`ActionPorts`](../../domain/action_ports.md): Carries an optional `IConfigService` into the action layer.
- [`SessionLoopGuard`](../../services/session_loop_guard.md): Reads the turn and cost guardrail limits.
- [`SessionPruningService`](../../services/session_pruning_service.md): Reads the `auto_pruning.*` settings.
- [`SessionService`](../../services/session_service.md): Reads session and provider settings.
- [CLI Adapter](../../../adapters/inbound/cli.md): Reads and persists settings during `init`, `start`, and `resume`.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; every implementing adapter overrides all four operations.
- `non_mutating_reads`: `get_config_path` and `get_setting` never mutate storage.
- `secret_isolation`: `set_env_variable` writes a secret to `.env` without mutating `os.environ`.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IConfigService`**: The driven contract consumed by core services and implemented by outbound adapters.

## Data Contracts
- **Configuration keys:** `yolo_default` (bool); `editor` (str); `execute.default_timeout_seconds` (float, default 60.0); `execute.max_output_lines` (int, default 100); `edit.similarity_threshold` (float, default 0.95); `read.max_lines` (int, default 1000); `research.max_results` (int, default 5); `context.max_tree_depth` (int, default 4, 0 = unlimited); `workspace.init` (bool, default true); `workspace.pre-commit` (bool, default true); `workspace.pull` (bool, default true); `checks.prompts` (bool); `checks.templates` (bool); `checks.update` (bool); `auto_pruning.enabled` (bool); `auto_pruning.turn_context_threshold` (int); `auto_pruning.prune_failure_history` (bool); `auto_pruning.prune_validation_failures` (bool); `auto_pruning.preserve_message_turns` (bool); `auto_pruning.max_turns_retention` (int); `llm.*` (passed through to LiteLLM).

## Operations

### `get_config_path() -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the path to the configuration file.

### `get_setting(key, default=None) -> Optional[Any]`
- **Preconditions:** `key` is a non-empty string.
- **Postconditions:** Returns the stored value, else `default`, else `None`.
- **Exceptions:** None — the contract guarantees a return value.

### `set_setting(key, value) -> None`
- **Preconditions:** `key` is a non-empty string.
- **Postconditions:** Updates and persists the value and refreshes the in-memory cache; dot-notation addresses nested keys.
- **Exceptions:** `OSError` when the file is unwritable; `yaml.YAMLError` when the file is corrupt.

### `set_env_variable(name, value) -> None`
- **Preconditions:** `name` is a non-empty environment-variable name.
- **Postconditions:** Persists the secret to the `.env` file in the config directory and leaves `os.environ` untouched.
- **Exceptions:** `OSError` when the `.env` file is unwritable.
