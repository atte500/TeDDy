# Component Design: YamlConfigAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/yaml_config_adapter.py`](/src/teddy_executor/adapters/outbound/yaml_config_adapter.py)

## Purpose
Implements the `IConfigService` outbound port. It reads a layered configuration from the bundled baseline plus `.teddy/config.yaml`, rejects a repeated key in the user config with a `ConfigurationError`, builds a typed schema view at load that fails fast on an uncoercible or out-of-range declared value, resolves `${VAR}` tokens, and persists settings and secrets without mutating the process environment.

## Consumers
- [`LiteLLMAdapter`](./litellm_adapter.md): Reads the `llm.*` settings and the API key.
- [`ActionPorts`](../../core/domain/action_ports.md): Carries an optional `IConfigService` into the action layer.
- [`SessionLoopGuard`](../../core/services/session_loop_guard.md): Reads the `guardrails.*` limits (with a legacy `yolo_guardrails.*` fallback).
- [`SessionPruningService`](../../core/services/session_pruning_service.md): Reads the `auto_pruning.*` settings.
- [`SessionService`](../../core/services/session_service.md): Reads session and provider settings.
- [CLI Adapter](../inbound/cli.md): Reads and persists settings during `init`, `start`, and `resume`.
- [Composition Root](/src/teddy_executor/container.py): Constructs the adapter with the config path.

## Dependencies
- **`yaml`** (external): Parses the baseline and the user configuration.
- **`dotenv`** (external): Reads and writes the sibling `.env` file.
- **`importlib.resources`** (stdlib): Loads the bundled baseline `config.yaml`.

## Class Invariants
- `layered_cache`: The merged configuration is cached in `_config` on first load and rebuilt from disk after every write.
- `duplicate_key_policy`: The user config fails fast with a `ConfigurationError` on any repeated mapping key at any depth. The bundled baseline stays permissive.
- `exact_key_precedence`: An exact top-level dotted key wins over the nested key in both `get_setting` and `set_setting`.
- `interpolation_order`: `${VAR}` tokens resolve before schema construction, and the live walk resolves them on each `get_setting` call.
- `env_layering`: The interpolation lookup layers `.env` values under `os.environ`, and reads `.env` fresh on every call.
- `no_os_environ_mutation`: `set_env_variable` writes the secret to `.env` only and never mutates `os.environ`.
- `comment_preserving_write`: `set_setting` rewrites only the target value token as raw text and never round-trips the document through `yaml.dump`.
- `typed_view_refresh`: The typed view rebuilds at construction and after every write, so a read reflects the persisted value.
- `declared_key_routing`: A declared key resolves through the typed view, while an undeclared key and every `llm.*` key resolve through the live dict walk.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IConfigService`**: The driven contract implemented by this adapter. See the [IConfigService design](../../core/ports/outbound/config_service.md).

## Data Contracts
- **`get_setting` return:** `Optional[Any]` — the resolved value, the supplied default, or `None`.
- **`.env` file:** A sibling of the config file, written with quoted values through `dotenv.set_key`.
- **Interpolation forms:** `${VAR}` (empty string when unresolved), `${VAR:-default}` (fallback value), and `$$` (literal `$`).
- **Typed schema:** The adapter builds an `AppConfig` from the interpolated merged mapping at construction, so an uncoercible or out-of-range declared value raises `ConfigurationError` at load. Every `llm.*` key bypasses the typed schema and reads from the live mapping.

## Operations

### `get_setting(key, default=None) -> Optional[Any]`
- **Preconditions:** `key` is a non-empty string.
- **Postconditions:** A declared key resolves through the typed view, so it carries the canonical schema default and declared type. An undeclared key and every `llm.*` key resolve through the live dict walk, where an exact top-level key wins over dot-notation resolution. A missing key returns `default`.
- **Exceptions:** None — the contract always returns a value.

### `set_setting(key, value) -> None`
- **Preconditions:** `key` is a non-empty string.
- **Postconditions:** Rewrites only the target value token, preserving comments and ordering, rebuilds the merged cache from disk, and refreshes the typed view. An exact top-level dotted key wins over a nested key. Dot-notation creates intermediate mappings.
- **Exceptions:** `OSError` when the file is unwritable; `yaml.YAMLError` when serialization fails; `ConfigurationError` when the file gained a duplicate key after the adapter loaded it.

### `get_config_path() -> str`
- **Postconditions:** Returns the configured path to the user config file.

### `set_env_variable(name, value) -> None`
- **Preconditions:** `name` is a non-empty environment-variable name.
- **Postconditions:** Persists the secret to the sibling `.env` file and leaves `os.environ` untouched.
- **Exceptions:** `OSError` when the `.env` file is unwritable.
