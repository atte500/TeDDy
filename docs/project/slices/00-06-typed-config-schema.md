# Slice: Typed Config Schema
- **Status:** Planned
- **Milestone:** N/A (ad-hoc)
- **Depends On:** [00-05](/docs/project/slices/00-05-workspace-config-improvements.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [IConfigService](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `typed-config`

## Goal
Replace scattered call-site defaults with one typed declaration of every key, type, range, and canonical default. The end-user `config.yaml` file keeps the same shape after this slice. The schema is an internal layer that validates at load time and exposes typed accessors, while `get_setting` remains compatible for consumers that have not yet migrated.

## Context

- `YamlConfigAdapter.get_setting(key, default)` returns raw values with call-site defaults. A typo silently returns the fallback.
- Defaults live at call sites:
    - `execute.default_timeout_seconds` falls back to `60.0` in `action_factory.py`.
    - `edit.similarity_threshold` falls back to `DEFAULT_SIMILARITY_THRESHOLD` in `action_factory.py` and `validation_rules/helpers.py`.
    - `execute.max_output_lines` is read without a default in `infrastructure.py`.
- There is no type checking, no range validation, and no single default table.
- `config_service.md` drift was repaired inside `00-05`. The typed schema prevents the entire drift class, because the schema becomes the port contract.
- Interpolation tokens (`${VAR}`) resolve inside the adapter. The schema must consume interpolated values.

## Scenarios

> As a maintainer, I want one constant to change when a canonical default changes, so every consumer picks it up. I want a misspelled key to fail at load time rather than silently return the fallback.

```gherkin
Given a bundled config.yaml with execute.default_timeout_seconds of 60
When the schema is constructed and a consumer reads config.execute.default_timeout_seconds on a user config that omits the key
Then the value is 60.0 and no call-site default is consulted

Given a user config that carries execute.max_output_lines: "one hundred"
When the adapter loads the config
Then a ConfigurationError is raised naming the key, the expected type, and the offending value
And the session fails fast before planning
```

> As a consumer of the schema, I want typed accessors and backward-compatible string lookups so I can migrate at my own pace.

```gherkin
Given the typed schema is constructed
When a caller uses config.get_setting("execute.max_output_lines")
Then the value equals config.execute.max_output_lines
```

## Edge Cases

- **Schema field absent from merged YAML:** Use the schema default. Validation passes.
- **Merged YAML value of the wrong type:** Raise `ConfigurationError` naming the key, the declared type, and the actual value.
- **Merged YAML value outside the declared range:** Raise `ConfigurationError`. Ranges cover `edit.similarity_threshold ∈ [0.0, 1.0]`, `context.max_tree_depth ≥ 0`, and any positive-only integer.
- **Unknown key in user YAML:** Ignore with a debug log. Forward compatibility wins over strict rejection, because future releases add keys.
- **Interpolation:** Interpolation runs before schema construction so a `${VAR}` resolves to a real value. A value that resolves to empty uses the schema default.
- **`get_setting` compatibility:** The compatibility path resolves through the schema when the key is known and falls back to the legacy dict walk when the key is not. This preserves any consumer still using string lookups.
- **Frozen dataclasses:** Each schema group is a frozen dataclass, so no consumer can mutate a resolved value.
- **`config.yaml` shape:** The bundled and user files remain unchanged. The schema is constructed from the merged dict; nothing writes to disk.

## Impact

1. `[NEW]` `core/domain/models/config_schema.py` — One frozen dataclass per group (`ExecuteConfig`, `EditConfig`, `ContextConfig`, `WorkspaceConfig`, `ReadConfig`, `ResearchConfig`, `ChecksConfig`, `AutoPruningConfig`, `GuardrailsConfig`, `LlmConfig`, and a top-level `AppConfig` that aggregates them). A shared `DEFAULT_APP_CONFIG` instance holds the canonical defaults.
2. `[EXPAND]` `YamlConfigAdapter.__init__` — Build an `AppConfig` immediately after `_load_layered_config` returns. Expose it as `self.app_config`.
3. `[EXPAND]` `YamlConfigAdapter.get_setting` — Route known keys through `app_config` and keep the legacy dict walk as the fallback for unknown keys.
4. `[MIGRATE]` Consumers — Move from `get_setting(key, default)` to `config.app_config.<group>.<field>` on a per-consumer basis.
5. `[CONTRACT]` `docs/architecture/core/ports/outbound/config_service.md` — Document that the schema is now the canonical default table. This is the point where the port doc stops drifting because the schema source and the doc are checked together in a test.

## Deliverables

- [ ] **Contract** — Create `src/teddy_executor/core/domain/models/config_schema.py` with one frozen dataclass per group and a top-level `AppConfig` aggregator. Provide a module-level `DEFAULT_APP_CONFIG = AppConfig()` instance that holds the canonical defaults from the current `config.yaml`.
- [ ] **Contract** — Add a `_construct_app_config(merged: dict) -> AppConfig` helper that walks each group, coerces values to the declared type where coercion is safe, applies the declared range, and raises `ConfigurationError` when a value is not coercible or is out of range.
- [ ] **Wiring** — In `YamlConfigAdapter.__init__`, after `_load_layered_config`, call `self.app_config = _construct_app_config(self._config)`. Also rebuild `self.app_config` in `set_setting` after the merged cache reload so the typed view stays consistent.
- [ ] **Wiring** — Route `get_setting` through `self.app_config` for known keys, preserving the exact-match-then-nested-fallback order.
- [ ] **Harness** — Add `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_typed_schema.py` covering: default resolution, wrong-type rejection, out-of-range rejection, unknown-key tolerance, interpolation-before-schema, and `get_setting` parity for every schema-declared key.
- [ ] **Harness** — Add `tests/suites/unit/core/domain/models/test_config_schema.py` that asserts every key documented in `config_service.md` exists in the schema and can be reached via `get_setting`. This closes the drift cycle.

## Implementation Notes

- The schema is additive. It does not change `config.yaml`. It does not change `get_setting` for keys that were previously resolving correctly.
- Consumer migration is incremental. This slice does not mandate that every consumer switches. The compatibility path preserves behavior during migration.
- Type coercion is conservative. `"100"` coerces to `100` when the declared type is `int` and the string parses cleanly. Any string that fails to parse raises. Booleans accept `true`, `false`, `yes`, `no`, `on`, `off` case-insensitively.
- Frozen dataclasses keep consumers honest: any attempt to mutate a field raises `FrozenInstanceError`.
- The `AppConfig` aggregator carries the same names and nesting as the YAML structure so the mental mapping stays trivial.

## Verification

1. **Default resolution:**
   Remove `execute.max_output_lines` from a scratch config. Confirm `get_setting("execute.max_output_lines")` and `app_config.execute.max_output_lines` both return `100`.
2. **Type rejection:**
   Set `execute.max_output_lines: "one hundred"`. Confirm the adapter raises `ConfigurationError` on load.
3. **Range rejection:**
   Set `edit.similarity_threshold: 1.5`. Confirm the adapter raises `ConfigurationError` on load.
4. **Drift closure:**
   Run `make test`. Confirm `test_config_schema.py` passes, proving that every documented key exists in the schema.
