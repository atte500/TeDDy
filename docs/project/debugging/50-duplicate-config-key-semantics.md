# Bug: Duplicate Config Keys Silently Diverge Between Read and Write
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Expected behavior: the load stops with a clear configuration error when a parameter appears more than once in `.teddy/config.yaml`. The approved policy is fail-fast on duplicates.
Actual behavior: the loader silently keeps the last occurrence and the writer silently rewrites the first occurrence, so a persisted write is ignored.

Minimal reproduction steps:
1. Create `.teddy/config.yaml` with two entries for the same key:
   ```yaml
   editor: first
   editor: second
   ```
2. Load the adapter and call `set_setting("editor", "third")`.
3. The file now contains `editor: third` followed by `editor: second`.
4. Reload the adapter and call `get_setting("editor")`. It returns `second`, not `third`.

A second form expresses one parameter in two shapes:
   ```yaml
   llm:
     model: nested-value
   "llm.model": flat-value
   ```
`get_setting("llm.model")` returns `flat-value`, while `set_setting("llm.model", "new")` rewrites only the nested entry. The next read still returns `flat-value`.

## Context & Scope
### Regressing Delta
None. The behavior is not a regression. The comment-preserving write path and the `yaml.safe_load` read path have never shared a duplicate-key contract.

### Environmental Triggers
A user config that repeats a key, or that combines a nested mapping with an exact top-level dotted key. The defect is operating-system independent and does not depend on the LLM provider or the editor.

### Ruled Out
- PyYAML does not reject duplicate keys. It silently keeps the last scalar value and the last mapping. Confirmed by a parser probe.
- The layer merge does not create the divergence. The collapse happens inside one document before the merge runs.
- Nested resolution in `get_setting` is not faulty. Exact top-level key precedence is documented and intentional.
- A flow-mapping ancestor such as `llm: {model: old}` is a pre-existing insertion limitation. The fix leaves that shape unchanged, so it stays outside this case's scope.

## Diagnostic Analysis
### Causal Model
1. `_load_user_config` passes the file through `yaml.safe_load`, which builds a mapping and keeps the last value for a repeated scalar key. For a repeated mapping key, the last mapping replaces the earlier one, so the earlier mapping's sibling keys disappear before the merge.
2. `_merge_dicts` merges that already-collapsed mapping into the bundled baseline. The baseline then fills any key the user document lost.
3. `set_setting` calls `_find_key_line`, which returns the first line whose computed path equals the requested path. The rewrite therefore lands on an occurrence that the loader ignores.
4. `get_setting` checks the exact top-level key before nested resolution. A flat `"llm.model"` key therefore shadows the nested key that `set_setting` writes.
5. The enforced policy removes this behavior. `_strict_load` rejects a repeated mapping key before `safe_load` collapses it, and `set_setting` rewrites the exact location that `get_setting` resolves.

### Discrepancies
- [x] `set_setting` rewrites the first duplicate while `safe_load` reads the last. (Resolved: a runtime probe kept both lines and the reload returned the second value.)
- [x] A repeated mapping key drops the sibling values of the earlier mapping. (Resolved: a probe lost `max_output_lines: 5`, fell back to the baseline 100, and kept `similarity_threshold: 0.5` from the second mapping.)
- [x] An exact top-level dotted key shadows the nested key written by `set_setting`. (Resolved: a probe returned the flat value after the nested write.)
- [x] A persisted setting can be silently ignored, and no warning or error reaches the user. (Resolved: a duplicate now stops the load with a `ConfigurationError` that names the key and its line, and `set_setting` writes the exact location that `get_setting` reads.)

### Investigation History
1. Read `yaml_config_adapter.py` and found `yaml.safe_load` on the load path and a raw-text `_find_key_line` scan on the write path. Hypothesized that the two paths resolve duplicates differently.
2. Read `test_yaml_config_adapter_layering.py` and confirmed coverage for baseline and user precedence, but no duplicate-key case.
3. Ran a temp-directory probe against the real adapter. Observed last-wins parsing, a first-line rewrite, an unchanged value after reload, flat-key shadowing, and the loss of sibling keys. Confirmed the divergence.
4. Ran `git grep` across the adapter tests for duplicate, twice, last wins, and first occurrence. It returned no matches, which confirms the behavior is unguarded.
5. Read the adapter architecture contract. It documents exact top-level key precedence but says nothing about duplicate keys or write/read agreement.
6. Created the preserved MRE at `spikes/debug/duplicate-config-key-semantics/01-duplicate-config-key-mre.py`. It reproduced all three divergence modes against the production adapter.
7. Built a sandbox replica with strict duplicate rejection, quoted-key normalization, exact-key precedence, and a disk-driven cache rebuild. Ten verification checks passed, including the unhashable-key fallback and the quoted nested key rewrite.
8. Audited the impact. Only the composition root (`registries/infrastructure.py`) and tests construct the adapter. No production module calls a private helper. The startup handlers catch `ConfigurationError` and print the configuration path hint.
9. Applied the proven fix to the production adapter with six regression tests. The targeted adapter modules passed 41 tests, and `make test` finished with 1875 passed and 5 skipped.
10. Retargeted the MRE to assert the enforced policy. It now exits 0 on the fixed adapter and exits 1 if either defect returns.

## Solution
### Root Cause
Verified by probe. The load path and the write path resolved a repeated occurrence in opposite directions: `yaml.safe_load` kept the last occurrence, and `_find_key_line` returned the first. The adapter also read an exact top-level dotted key before a nested key, while `set_setting` always wrote the nested location. Neither path warned or failed.

The approved policy is fail-fast, recorded on 2026-10-19. The fix was proven in the sandbox replica and then applied directly to production. The user config now parses through `_strict_load`, which raises a `ConfigurationError` that names the duplicated key and its line. The baseline config keeps the permissive loader. `_find_key_line` normalizes quoted key tokens. `_surgically_set` prefers the exact top-level dotted key, matching the read precedence. `set_setting` rebuilds the merged cache from disk after each write, so the cache cannot diverge from the file.

The targeted adapter modules passed 41 tests. The full suite finished with 1875 passed and 5 skipped.

### Affected Components
- `YamlConfigAdapter._load_user_config`: now parses the user config through `_strict_load`, which rejects a repeated mapping key at any depth. The baseline loader stays permissive.
- `YamlConfigAdapter._find_key_line`: now normalizes quoted key tokens, so `"llm.model": value` matches the dotted path.
- `YamlConfigAdapter._surgically_set`: now prefers an exact top-level dotted key line, matching the `get_setting` precedence.
- `YamlConfigAdapter.set_setting`: now rebuilds the merged cache from disk after a write.
- `tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py`: six regression tests cover duplicate scalar, nested, and mapping keys, exact-key precedence, a quoted nested key, and the unhashable-key fallback.
- `docs/architecture/adapters/outbound/yaml_config_adapter.md`: documents the duplicate-key policy, the exact-key precedence, and the new exception.
- [Preserved MRE](/spikes/debug/duplicate-config-key-semantics/01-duplicate-config-key-mre.py): asserts the enforced policy and exits 0 on the fixed adapter.
- [Replica proof](/spikes/debug/duplicate-config-key-semantics/02-verify-replica-fix.py): ten verification checks against the [sandbox replica](/spikes/debug/duplicate-config-key-semantics/replica_yaml_config_adapter.py).
