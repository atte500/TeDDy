# Bug: Duplicate Config Keys Silently Diverge Between Read and Write
- **Status:** Unresolved
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

## Diagnostic Analysis
### Causal Model
1. `_load_user_config` passes the file through `yaml.safe_load`, which builds a mapping and keeps the last value for a repeated scalar key. For a repeated mapping key, the last mapping replaces the earlier one, so the earlier mapping's sibling keys disappear before the merge.
2. `_merge_dicts` merges that already-collapsed mapping into the bundled baseline. The baseline then fills any key the user document lost.
3. `set_setting` calls `_find_key_line`, which returns the first line whose computed path equals the requested path. The rewrite therefore lands on an occurrence that the loader ignores.
4. `get_setting` checks the exact top-level key before nested resolution. A flat `"llm.model"` key therefore shadows the nested key that `set_setting` writes.

### Discrepancies
- [x] `set_setting` rewrites the first duplicate while `safe_load` reads the last. (Resolved: a runtime probe kept both lines and the reload returned the second value.)
- [x] A repeated mapping key drops the sibling values of the earlier mapping. (Resolved: a probe lost `max_output_lines: 5`, fell back to the baseline 100, and kept `similarity_threshold: 0.5` from the second mapping.)
- [x] An exact top-level dotted key shadows the nested key written by `set_setting`. (Resolved: a probe returned the flat value after the nested write.)
- [ ] A persisted setting can be silently ignored, and no warning or error reaches the user.

### Investigation History
1. Read `yaml_config_adapter.py` and found `yaml.safe_load` on the load path and a raw-text `_find_key_line` scan on the write path. Hypothesized that the two paths resolve duplicates differently.
2. Read `test_yaml_config_adapter_layering.py` and confirmed coverage for baseline and user precedence, but no duplicate-key case.
3. Ran a temp-directory probe against the real adapter. Observed last-wins parsing, a first-line rewrite, an unchanged value after reload, flat-key shadowing, and the loss of sibling keys. Confirmed the divergence.
4. Ran `git grep` across the adapter tests for duplicate, twice, last wins, and first occurrence. It returned no matches, which confirms the behavior is unguarded.
5. Read the adapter architecture contract. It documents exact top-level key precedence but says nothing about duplicate keys or write/read agreement.

## Solution
### Root Cause
Verified by probe. The load path and the write path resolve a repeated occurrence in opposite directions: `yaml.safe_load` keeps the last occurrence, and `_find_key_line` returns the first. The adapter also reads an exact top-level dotted key before a nested key, while `set_setting` always writes the nested location. Neither path warns or fails. Product decision recorded on 2026-10-19: fail fast. The load path must reject any duplicate key in the user config with a clear configuration error. No fix is applied yet.

### Affected Components
- `YamlConfigAdapter._find_key_line`: must select the occurrence that the loader honours. Once the loader rejects duplicates, this scan only sees unique keys.
- `YamlConfigAdapter.set_setting`: must honour the same precedence as `get_setting`, including an exact top-level dotted key.
- `YamlConfigAdapter._load_user_config`: must detect duplicate keys and raise a clear configuration error instead of silently collapsing them.
- `tests/suites/unit/adapters/outbound/test_yaml_config_adapter*.py`: need coverage for duplicate keys and exact-key precedence.
- `docs/architecture/adapters/outbound/yaml_config_adapter.md`: must state the chosen duplicate-key semantics.
