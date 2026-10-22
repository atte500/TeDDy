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

1. `[NEW]` `core/domain/models/config_schema.py` — One frozen dataclass per fixed group (`ExecuteConfig`, `EditConfig`, `ContextConfig`, `WorkspaceConfig`, `ReadConfig`, `ResearchConfig`, `ChecksConfig`, `AutoPruningConfig`, `GuardrailsConfig`) and a top-level `AppConfig` that aggregates them. `llm` stays a passthrough mapping because consumers read the whole group as a dict, so no `LlmConfig` dataclass exists. A shared `DEFAULT_APP_CONFIG` instance holds the canonical defaults.
2. `[EXPAND]` `YamlConfigAdapter.__init__` — Build an `AppConfig` immediately after `_load_layered_config` returns. Expose it as `self.app_config`.
3. `[EXPAND]` `YamlConfigAdapter.get_setting` — Route known keys through `app_config` and keep the legacy dict walk as the fallback for unknown keys.
4. `[MIGRATE]` Consumers — Move from `get_setting(key, default)` to `config.app_config.<group>.<field>` on a per-consumer basis.
5. `[CONTRACT]` `docs/architecture/core/ports/outbound/config_service.md` — Document that the schema is now the canonical default table. This is the point where the port doc stops drifting because the schema source and the doc are checked together in a test.

## Deliverables

### Section A: Typed Schema Core

- [ ] **Wiring** — Acceptance tracer bullet for the fail-fast typed-config boundary. Add `tests/suites/acceptance/test_typed_config_schema.py` driving the public `teddy start` path with `execute.max_output_lines: "one hundred"` and asserting exit code 1 plus a `ConfigurationError` line naming the key. Green skeleton: create `src/teddy_executor/core/domain/models/config_schema.py` with the frozen group dataclasses and `DEFAULT_APP_CONFIG`, add `_construct_app_config(merged)` that returns `DEFAULT_APP_CONFIG` and performs one hardcoded coercion guard for `execute.max_output_lines`, and call it from `YamlConfigAdapter.__init__` to store `self.app_config`. No user override flows yet, because `get_setting` still reads the live dict.
- [ ] **Logic** — Replace the skeleton with full per-key construction: resolve each declared key with exact-flat-first then nested precedence, coerce strings to the declared type where safe (`int`, `float`, `bool` with true/false/yes/no/on/off), fall back to the schema default for a missing value, ignore unknown keys with a debug log, and raise `ConfigurationError` naming the key, the expected type, and the offending value when coercion fails. Unit tests drive each path.
- [ ] **Logic** — Apply the declared ranges: `edit.similarity_threshold` in `[0.0, 1.0]`, `context.max_tree_depth` at least 0, and positive-only capacities `execute.max_output_lines`, `read.max_lines`, and `research.max_results` at least 1. An out-of-range value raises `ConfigurationError`. Unit tests drive each range.
- [ ] **Wiring** — Rebuild `self.app_config` in `set_setting` after the merged cache reload, so the typed view tracks a write. A unit test asserts `app_config` reflects a `set_setting` change.
- [ ] **Wiring** — Route `get_setting` through `self.app_config` for known declared keys, preserving the exact-match-then-nested order, and fall back to the live dict walk for unknown keys and every `llm.*` key. Parity and `llm.api_key` liveness unit tests pin the contract.
- [ ] **Harness** — Add `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_typed_schema.py` covering default resolution, wrong-type rejection, out-of-range rejection, unknown-key tolerance, interpolation-before-schema, and `get_setting` parity for every schema-declared key.
- [ ] **Harness** — Add `tests/suites/unit/core/domain/models/test_config_schema.py` that asserts every key documented in `config_service.md` (except the `llm.*` passthrough) exists in the schema and can be reached via `get_setting`. This closes the drift cycle.
- [ ] **Cleanup** — Update `docs/architecture/core/ports/outbound/config_service.md` to name the schema as the canonical default table and to record that `llm.*` stays a passthrough mapping on the live walk.

## Implementation Notes

- Orientation audit re-partitioned this slice into eight atomic deliverables with Wiring first. Evidence forced three design corrections. First, `llm` stays a passthrough mapping because `litellm_adapter.py` reads the whole group with `get_setting("llm", {})`, so no fixed `LlmConfig` dataclass exists. Second, `llm.api_key` stays on the live dict walk because the API-key prompt writes `.env` then preflight reads the value in the same process, and a construction-time snapshot would go stale. Third, `_construct_app_config` resolves each declared key with exact-flat-first-then-nested precedence to keep `get_setting` parity. Range validation is limited to `edit.similarity_threshold`, `context.max_tree_depth`, and the three positive-only capacities, because those are the only ranges with test-write evidence.
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
