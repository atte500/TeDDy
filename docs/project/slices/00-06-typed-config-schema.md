# Slice: Typed Config Schema
- **Status:** In Progress
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

- [x] **Wiring** — Acceptance tracer bullet for the fail-fast typed-config boundary. Add `tests/suites/acceptance/test_typed_config_schema.py` driving the public `teddy start` path with `execute.max_output_lines: "one hundred"` and asserting exit code 1 plus a `ConfigurationError` line naming the key. Green skeleton: create `src/teddy_executor/core/domain/models/config_schema.py` with the frozen group dataclasses and `DEFAULT_APP_CONFIG`, add `_construct_app_config(merged)` that returns `DEFAULT_APP_CONFIG` and performs one hardcoded coercion guard for `execute.max_output_lines`, and call it from `YamlConfigAdapter.__init__` to store `self.app_config`. No user override flows yet, because `get_setting` still reads the live dict.
- [x] **Logic** — Replace the skeleton with full per-key construction: resolve each declared key with exact-flat-first then nested precedence, coerce strings to the declared type where safe (`int`, `float`, `bool` with true/false/yes/no/on/off), fall back to the schema default for a missing value, ignore unknown keys with a debug log, and raise `ConfigurationError` naming the key, the expected type, and the offending value when coercion fails. Unit tests drive each path.
- [x] **Logic** — Apply the declared ranges: `edit.similarity_threshold` in `[0.0, 1.0]`, `context.max_tree_depth` at least 0, and positive-only capacities `execute.max_output_lines`, `read.max_lines`, and `research.max_results` at least 1. An out-of-range value raises `ConfigurationError`. Unit tests drive each range.
- [x] **Wiring** — Rebuild `self.app_config` in `set_setting` after the merged cache reload, so the typed view tracks a write. A unit test asserts `app_config` reflects a `set_setting` change.
- [x] **Wiring** — Route `get_setting` through `self.app_config` for known declared keys, preserving the exact-match-then-nested order, and fall back to the live dict walk for unknown keys and every `llm.*` key. Parity and `llm.api_key` liveness unit tests pin the contract.
- [x] **Harness** — Add `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_typed_schema.py` covering default resolution, wrong-type rejection, out-of-range rejection, unknown-key tolerance, interpolation-before-schema, and `get_setting` parity for every schema-declared key.
- [x] **Harness** — Add `tests/suites/unit/core/domain/models/test_config_schema.py` that asserts every key documented in `config_service.md` (except the `llm.*` passthrough) exists in the schema and can be reached via `get_setting`. This closes the drift cycle.
- [x] **Cleanup** — Update `docs/architecture/core/ports/outbound/config_service.md` to name the schema as the canonical default table and to record that `llm.*` stays a passthrough mapping on the live walk.

## Implementation Notes

- Orientation audit re-partitioned this slice into eight atomic deliverables with Wiring first. Evidence forced three design corrections. First, `llm` stays a passthrough mapping because `litellm_adapter.py` reads the whole group with `get_setting("llm", {})`, so no fixed `LlmConfig` dataclass exists. Second, `llm.api_key` stays on the live dict walk because the API-key prompt writes `.env` then preflight reads the value in the same process, and a construction-time snapshot would go stale. Third, `_construct_app_config` resolves each declared key with exact-flat-first-then-nested precedence to keep `get_setting` parity. Range validation is limited to `edit.similarity_threshold`, `context.max_tree_depth`, and the three positive-only capacities, because those are the only ranges with test-write evidence.
- The schema is additive. It does not change `config.yaml`. It does not change `get_setting` for keys that were previously resolving correctly.
- Consumer migration is incremental. This slice does not mandate that every consumer switches. The compatibility path preserves behavior during migration.
- Type coercion is conservative. `"100"` coerces to `100` when the declared type is `int` and the string parses cleanly. Any string that fails to parse raises. Booleans accept `true`, `false`, `yes`, `no`, `on`, `off` case-insensitively.
- Frozen dataclasses keep consumers honest: any attempt to mutate a field raises `FrozenInstanceError`.
- The `AppConfig` aggregator carries the same names and nesting as the YAML structure so the mental mapping stays trivial.
- Section A fail-fast Wiring deliverable landed the first typed-config boundary end to end. `config_schema.py` now holds the frozen group dataclasses, the `DEFAULT_APP_CONFIG` aggregate, a precedence-faithful `_lookup` that tries the exact flat dotted key before the nested walk, an `_coerce_int` guard, and a `construct_app_config` skeleton that validates only `execute.max_output_lines` and returns the default aggregate. `YamlConfigAdapter.__init__` stores `self.app_config = construct_app_config(self._config)` immediately after the layered load, so construction fails before planning when a declared value cannot be coerced. `__main__.py` gained `_resolve_config_or_exit`, which prints `Error: <message>` and exits 1 on a `ConfigurationError`, and both `start` and `resume` route through it. The `execute` command was intentionally left on a plain `container.resolve(IConfigService)`, because the tracer bullet scopes the fail-fast boundary to the session start and resume paths. The Red step drove the real `teddy start` path through the new acceptance module with `execute.max_output_lines: "one hundred"` and observed exit code 0 with no key in output, which proved the boundary was reachable and the guard absent. The Green step landed the schema, the adapter wiring, and the boundary catch, and the acceptance module then passed with the key and value in the error line. The Refactor step consolidated the triplicated coercion error message into one local string, and the focused module stayed at `1 passed`. The unfiltered suite passed 2078 tests with 5 skipped, so no existing caller regressed from the new adapter attribute or the boundary catch.
- Section A full per-key construction Logic deliverable replaced the single-key skeleton with a declarative field table and typed coercion. A frozen `_FieldSpec` records each key, its target group, target field, and type, and `_SCHEMA_FIELDS` enumerates all twenty-two group fields, including the hyphenated `workspace.pre-commit` YAML key that maps to the `pre_commit` Python field. `_coerce_int`, `_coerce_float`, and `_coerce_bool` accept a real value or a safe string, and `_coerce_bool` recognises `true`/`false`, `yes`/`no`, and `on`/`off` case-insensitively. Construction reads each key through the precedence-faithful `_lookup`, skips an absent or empty value so the dataclass default applies, records each undeclared top-level group at debug level, and builds every group. Range validation stays out of this deliverable because the next Logic item owns it. The Red step ran the new `tests/suites/unit/core/domain/models/test_config_schema.py` and reported `12 failed, 3 passed`, where the passing cases were the missing-defaults, unknown-key, and uncoercible-integer guards the skeleton already satisfied. The Green step landed the full construction and the focused module then passed 15 tests. The unfiltered suite passed 2093 tests with 5 skipped, which is fifteen over the 2078 baseline because the new unit module adds fifteen cases.

- Section A range-validation Logic deliverable made the bounds declarative beside each field. The frozen `_FieldSpec` gained inclusive `minimum` and `maximum` members, where a `None` bound leaves that side unbounded, so a spec without bounds accepts any coercible value. Exactly five keys declare bounds, namely `execute.max_output_lines` with a minimum of 1, `edit.similarity_threshold` inside the closed interval zero to one, `read.max_lines` with a minimum of 1, `context.max_tree_depth` with a minimum of 0, and `research.max_results` with a minimum of 1. A new `_validate_range` helper sits beside `_coerce` and rejects a value below the minimum or above the maximum with a `ConfigurationError` naming the key, the expected bound, and the offending value. `construct_app_config` applies it at the single coercion-and-assignment seam, so every declared field flows through one guard and no second bound table can drift. The construction docstring now records range rejection beside type rejection. The Red step ran the extended `test_config_schema.py` and reported `6 failed, 21 passed`, where every failure was `DID NOT RAISE ConfigurationError` on a range case and the boundary and capacity cases stayed green, which confirmed the range is meant to be inclusive. The Green step then landed the declarative bounds and the guard, and the focused module passed 27 tests. The unfiltered suite passed 2105 tests with 5 skipped, which is twelve over the 2093 baseline because the range deliverable adds twelve parameterized cases. An in-plan prediction of 2099 undercounted that parametrized expansion, so the observed 2105 is the correct count and no defect.

- Section A typed-view rebuild Wiring deliverable made the typed view track a write. `YamlConfigAdapter.__init__` now builds the view through a new `_refresh_typed_view` helper, so one method owns the construction invariant, and `set_setting` calls the same helper directly after it rebuilds `self._config` from disk. The rebuild sits after the `self._config.clear()` and `self._config.update(merged)` reload, so `app_config` reflects the persisted value while the surgical write keeps the user file intact. The Red step added `test_set_setting_rebuilds_the_typed_view` to `test_yaml_config_adapter.py`, which writes `execute.max_output_lines` and asserts the pre-write view reads 100 and the post-write view reads 250. It failed with `assert 100 == 250`, proving the view was a frozen `__init__` snapshot that never refreshed after a write. The Green step landed the helper and the rebuild call, and the focused case then passed. The unfiltered suite passed 2106 tests with 5 skipped, which is one over the 2105 baseline because the new case adds one test and removes none.
- Section A get_setting routing Wiring deliverable routed declared keys through the typed view. `config_schema.py` derives `_DECLARED_KEY_TARGETS` from the single `_SCHEMA_FIELDS` table, so no second key list can drift. `is_declared_key` tests membership, and `read_declared_value` reads the typed field behind a native `assert is_declared_key(key)` contract. `yaml_config_adapter.py` gained `_PASSTHROUGH_KEY_PREFIX = "llm."`, and `get_setting` routes through the typed view only when the key is not a passthrough prefix and is declared, so every other key, including unknown keys and the whole `llm.*` group, keeps the live walk. The Red step added two cases to `test_yaml_config_adapter.py`: the parity case wrote `execute.max_output_lines: '200'` and failed with `assert '200' == 200`, proving the raw string was returned while `app_config` held the coerced int, and the `llm.api_key` liveness guard passed, proving the passthrough path already stayed live. The Green step landed the derived map, the two helpers, and the routing branch, and the focused probe of the adapter and schema modules passed 30 tests. The unfiltered suite passed 2108 tests with 5 skipped, which is two over the 2106 baseline because the parity case and the liveness guard add two tests.
- Section A adapter typed-schema Harness deliverable added `test_yaml_config_adapter_typed_schema.py` with six cases. The cases pin default resolution, wrong-type rejection at load, out-of-range rejection at load, unknown-group tolerance, interpolation before schema coercion, and string-lookup parity with the typed view across every declared key. The Red step ran the new module and reported one failed and five passed. The failure was `test_interpolation_runs_before_schema_coercion`, which raised `ConfigurationError: Configuration key 'execute.max_output_lines' expected int, got '${TEDDY_TEST_MAX_LINES}'.` The traceback showed the raw token reaching `_coerce_int`, because `_refresh_typed_view` built the view from the uninterpolated merged config. The Green step wrapped the merged config with the existing `_maybe_interpolate` helper, so construction sees resolved values while the raw `self._config` stays live for `get_setting` fallbacks and every `llm.*` key. `_maybe_interpolate` returns a new mapping and never mutates its source. The focused module then passed six tests, and the unfiltered suite passed 2114 tests with 5 skipped, which is six over the 2108 baseline because the new module adds six tests.
- Section A drift-closure Harness deliverable extended `tests/suites/unit/core/domain/models/test_config_schema.py` with two cases that pin the documented key surface against the schema. The first case asserts every documented key is declared, and the second case asserts every documented key resolves through `get_setting` to its typed value. The Red step reported `2 failed, 27 passed`, where the first failure named `['yolo_default', 'editor']` and the second raised the native `read_declared_value` assertion naming `yolo_default`. The Green step declared both keys as top-level scalars with a `None` group, added a `str` coercion helper, added top-level `AppConfig` fields, and made the read and construct paths tolerate the `None` group. `_KNOWN_TOP_LEVEL` filters the `None` group so the known-group set gains no empty entry. Declaring `editor` moved the key into the typed view, so `test_get_setting_respects_caller_default_at_call_site` now reads the undeclared key `undeclared_setting` to preserve the caller-default contract. The focused schema and typed-schema probe passed 35 tests, and the unfiltered suite passed 2116 tests with 5 skipped.
- Section A config port-document Cleanup deliverable applied the as-built prose to `config_service.md`. The `## Data Contracts` section gained a **Canonical defaults** bullet naming `config_schema.py` as the single source of truth for every declared key, type, range, and default, and an **`llm.*` passthrough** bullet recording that every `llm.*` key bypasses the typed schema and reads from the live merged mapping on each `get_setting` call, because a construction-time snapshot goes stale after a mid-run `.env` write. The `get_setting` postconditions now state that a declared key resolves through the typed schema while an undeclared key and every `llm.*` key fall back to the live merged mapping. The `- **Configuration keys:**` line stayed byte-identical, so the `_documented_configuration_keys()` drift helper still parses the same key set. The Red step was the observed absence of any schema, canonical, or passthrough prose. The Green step applied the two edits, and the focused drift selection passed two cases. The unfiltered suite passed 2116 tests with 5 skipped, so the documentation change regresses no test.
- Section A adapter as-built update corrected `yaml_config_adapter.md` in five places. The Purpose now names the typed schema view and its load-time fail-fast. The stale `lazy_interpolation` invariant became `interpolation_order`, because interpolation runs before schema construction while the live walk interpolates on read. Two invariants record the typed-view refresh at construction and after every write, and the declared-key routing that leaves undeclared and `llm.*` keys on the live walk. The Data Contracts gained one typed-schema bullet, and the `get_setting` and `set_setting` postconditions record the typed-view routing and the post-write refresh. The drift helper reads the port document key line, so it stayed byte-identical.

## Verification

1. **Default resolution:**
   Remove `execute.max_output_lines` from a scratch config. Confirm `get_setting("execute.max_output_lines")` and `app_config.execute.max_output_lines` both return `100`.
2. **Type rejection:**
   Set `execute.max_output_lines: "one hundred"`. Confirm the adapter raises `ConfigurationError` on load.
3. **Range rejection:**
   Set `edit.similarity_threshold: 1.5`. Confirm the adapter raises `ConfigurationError` on load.
4. **Drift closure:**
   Run `make test`. Confirm `test_config_schema.py` passes, proving that every documented key exists in the schema.
