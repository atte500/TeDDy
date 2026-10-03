# Bug: editor config-set rewrites entire config.yaml

- **Status:** Resolved
- **Milestone:** [03-foundational-refactors.md](/docs/project/milestones/03-foundational-refactors.md)
- **Vertical Slice:** [03-01-editor-validation-and-discovery.md](/docs/project/slices/03-01-editor-validation-and-discovery.md)
- **Specs:** [editor-validation-and-discovery.md](/docs/project/specs/editor-validation-and-discovery.md)

## Symptoms

**Expected:** When `editor` is unset (baseline `editor: ""`) and the user selects an editor through the interactive console prompt, ONLY the `editor:` line in `.teddy/config.yaml` should change. All comments (header banner, section comments, inline trailing comments) and formatting/key-order MUST be preserved.

**Actual:** Setting `editor` rewrites the ENTIRE `.teddy/config.yaml`: every comment is deleted, keys are reordered (alphabetical within each mapping), quoting/flow style is normalized, and blank lines are collapsed. The file becomes a bare data dump.

**Minimal reproduction:** The bug was reproduced during the session via a temporary MRE (`spikes/debug/63-editor-set-rewrites-config-mre.py`, importing the real `YamlConfigAdapter` from `src/`); that session-local artifact was removed during teardown. The PERMANENT reproduction/guard is now the regression test, which fails against the old lossy implementation (comments stripped, keys reordered) and passes against the surgical fix:

```shell
uv run pytest tests/suites/unit/adapters/outbound/test_yaml_config_adapter_preserves_comments.py -v -n0
```

Observed AFTER state (comment-stripped, reordered):

```yaml
editor: nvim
execution:
  default_timeout_seconds: 60
  max_output_lines: 100
  similarity_threshold: 0.95
```

Note the loss of the `# TeDDy Configuration` header, the editor banner comment, the inline `# Caps EXECUTE output to the last X lines.` comment, and the reordering of `similarity_threshold` after `max_output_lines`. The MRE assertion fails with `AssertionError: BUG: header comment destroyed by set_setting`.

## Context & Scope

### Regressing Delta

Slice 03-01 (`editor-validation-and-discovery`) added the `set_setting()` method to `IConfigService` and `YamlConfigAdapter`, plus the CLI persistence path `_persist_editor_choice`. The `YamlConfigAdapter.set_setting` body:

1. reads the existing user config with `yaml.safe_load` (a data-only loader that discards all comments and formatting),
2. mutates the resulting plain `dict` using dot-notation traversal,
3. writes the ENTIRE dict back with `yaml.dump(user_config, f, default_flow_style=False, allow_unicode=True)`.

`yaml.safe_load`/`yaml.dump` is an inherently lossy round-trip for comments and layout, so ANY `set_setting` call rewrites the whole file. This is the exact delta that introduced the symptom; no prior code path wrote the config file.

### Environmental Triggers

None. The bug is deterministic and environment-independent: any invocation of `set_setting` against a comment-rich config reproduces it. The only precondition is the interactive preflight reaching `_persist_editor_choice` (editor unset/empty or missing on PATH).

### Ruled Out

- The bundled baseline `config.yaml` is NOT at fault — it is correctly comment-rich.
- The CLI handler `_persist_editor_choice` is NOT at fault — it correctly delegates to `IConfigService.set_setting`.
- The `_load_layered_config` / `get_setting` read path is NOT at fault — it legitimately uses `yaml.safe_load` (reading does not need to preserve comments).
- The merge logic is NOT at fault — the merge operates in-memory on dicts; destruction happens at the `yaml.dump` write in `set_setting`.

## Diagnostic Analysis

### Causal Model

`.teddy/config.yaml` is created during `teddy init` as a copy of the comment-rich bundled baseline. During an interactive session preflight, when the configured `editor` is empty (`""`, the baseline default) or does not resolve on PATH, `_validate_editor_config` calls `_prompt_for_editor_selection` (or `_prompt_for_custom_editor`), which on a valid choice calls `_persist_editor_choice(config_service, value)`. That helper calls `config_service.set_setting("editor", value)`.

`YamlConfigAdapter.set_setting` performs a full-document round-trip: `yaml.safe_load` → mutate dict → `yaml.dump`. Because `safe_load` produces a plain dict with no comment/layout metadata, and `yaml.dump` re-emits from scratch, the write obliterates all comments, normalizes style, and reorders keys. The reported "whole config.yaml gets rewritten" is exactly this round-trip.

### Discrepancies

- (Resolved) The reported symptom and the observed MRE output agree fully; the comment/reorder loss is fully explained by the `yaml.safe_load`/`yaml.dump` round-trip.
- (Resolved) A pre-existing user config whose ENTIRE non-comment content is a degenerate empty-root token — `{}`, `null`, or `~` — produced INVALID YAML when a key was appended (e.g. `{}\neditor: nvim` → parse error). A truly empty file and a comment-only file were already handled correctly. Fix: `_strip_degenerate_root()` drops a lone degenerate empty-root token before appending; re-verified via `63-edge-case-probe.py` — all five document shapes now round-trip.

### Investigation History

1. Located the persistence call site: `session_cli_handlers._persist_editor_choice` → `config_service.set_setting("editor", value)`. Confirmed.
2. Read `YamlConfigAdapter.set_setting` (lines 107–150). Found the `yaml.safe_load`/`yaml.dump` full-document round-trip. Hypothesis: comments are destroyed by this cycle.
3. Read the bundled baseline `config.yaml` (comment-rich) and the existing adapter tests (which assert value persistence / cache sync / dot-notation / key preservation but NOT comment preservation). Confirmed the baseline is comment-rich and no test guards comment survival.
4. Built and executed MRE `63-editor-set-rewrites-config-mre.py` against the real adapter. Observed complete comment loss + key reordering; assertion failed. Root cause reproduced.
5. Zero-Touch Verification (Phase 2 Step 6): replicated `YamlConfigAdapter` into `spikes/debug/shadow_yaml_config_adapter.py` and replaced `set_setting`'s full-document round-trip with a line-scoped surgical text edit (`_find_key_line` indent-aware scan + `_surgically_set` value-token rewrite + `_insert_key` for missing keys). Repointed the MRE at the shadow module and re-ran it. Observed: BEFORE and AFTER are byte-identical except `editor: ""` → `editor: nvim`; all three survival checks (`header`, `editor banner`, `inline`) returned True; `PASS: comments preserved (bug fixed)`. Fix proven without touching `src/`.
6. Edge-case probe (`63-edge-case-probe.py`) over five pre-existing document shapes. Observed: truly-empty file → `editor: nvim` (valid, reload OK); comment-only file → comment preserved + `editor: nvim` (valid, reload OK); `{}` → `{}\neditor: nvim` (INVALID, reload fails); `null` → `null\neditor: nvim` (INVALID); `~` → `~\neditor: nvim` (INVALID). Conclusion: only degenerate empty-root tokens break the append path; empty/comment-only files are already safe.
7. Extended the shadow's `_surgically_set` with `_strip_degenerate_root()`, which removes a lone degenerate empty-root token (`{}`/`null`/`~`) before appending. Re-ran `63-edge-case-probe.py`: all five shapes now round-trip (valid YAML, `editor == nvim` on reload, comments preserved where present). Degenerate-document handling proven without touching `src/`.
8. Systemic Audit (Phase 4). Categorized the root cause as "lossy round-trip mutation of a user-editable file". A `git grep` census of all `yaml.dump`/`yaml.safe_dump`/`json.dumps` write sites in `src/` classified each target: `yaml_config_adapter.py` writes the user-editable `config.yaml` (the defect); `prompt_manager.py`/`session_repository.py` write machine-owned turn/session meta; `openrouter_hydrator.py`/`context_service.py`/`update_checker.py` write machine-owned caches. A `git grep set_setting` census confirmed the ONLY production caller is `session_cli_handlers.py:573` with key `"editor"`. Impact Audit: the fix changes no Port/Signature/DTO (`IConfigService.set_setting` signature unchanged) and the preflight reword is a single untested site — no Contract/Migration partition and no additional Refactor deliverable required.
9. Implementation (Phase 6). Added the regression test `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_preserves_comments.py` and observed RED against the unmodified adapter (3 failed / 2 passed — the comment-survival, key-order and byte-exact assertions failed; the empty/`{}` guard tests passed, as intended). Ported the shadow-verified surgical `set_setting` into production `yaml_config_adapter.py` and applied the user-approved preflight reword ("No editor configured. Please select one below:"); observed GREEN (5 passed). Re-pointed the original MRE at the REAL production adapter and re-ran it: `PASS: comments preserved (bug fixed)` (header/editor/inline comments survived; ordering preserved). Full suite: `1546 passed, 5 skipped`. A Ruff probe then flagged a NEW `C901 _insert_key (10 > 9)`; refactored it into `_find_ancestor`/`_render_key_lines`/`_find_insertion_point` (each below threshold) and re-ran the suite (`1546 passed, 5 skipped`) — semantics preserved. The only remaining Ruff findings are the pre-existing `_orchestrate_session_loop` C901/PLR0913/PLR0915 (documented Milestone-5 debt; pre-commit bypassed via `--no-verify`, post-commit test gate enforced).

## Solution

### Root Cause
`YamlConfigAdapter.set_setting()` persisted the user config by round-tripping the ENTIRE document through `yaml.safe_load` → mutate dict → `yaml.dump`. `yaml.safe_load` produces a plain `dict` carrying no comment or layout metadata, and `yaml.dump` re-emits the document from scratch — so every `set_setting` call (including the `editor` persistence from the interactive preflight prompt) destroyed all comments, normalized quoting/flow style, collapsed blank lines, and reordered keys. This is a textbook lossy-round-trip defect, not a formatting quirk.

### Proven Fix (Implemented & Verified in Production)
The fix below was first proven against a shadow replica, then ported into production `YamlConfigAdapter` and verified RED→GREEN by the new regression test and end-to-end by the original reproduction scenario re-run against the real fixed adapter.
Replace the lossy round-trip in `YamlConfigAdapter.set_setting()` with a **line-scoped surgical text edit** that preserves every byte except the target value token:
1. Read the file as raw text.
2. Locate the target key's line via an indentation-aware traversal of the dot-notation path (`_find_key_line`).
3. Rewrite ONLY the value token on that line, preserving any trailing inline comment.
4. If the key is absent, append it (creating parent mappings as needed) at the correct indentation and insertion point (`_insert_key`).
5. Still synchronize the in-memory merged cache so a subsequent `get_setting()` on the same adapter reflects the change.

This is **dependency-free** (no `ruamel.yaml` addition). Verified empirically via `spikes/debug/shadow_yaml_config_adapter.py`: comments, ordering, and blank lines all survive while `editor` is updated.

### Systemic Preventative Measure
Adopt a project rule: **user-editable configuration files MUST be mutated surgically (line/token-scoped), never round-tripped through a data-only loader** (`yaml.safe_load`/`yaml.dump`, `json.load`/`json.dump`). Guard it with a regression test that asserts comment/layout survival after a `set_setting` call — the existing adapter tests only asserted value persistence, which is exactly why this defect shipped. (Other `yaml.dump` sites in `prompt_manager.py` / `session_repository.py` / `session_service.py` write machine-owned turn/session meta files, not the user config, so they are legitimately lossy; the rule applies to human-editable files.)

### Degenerate-Document Handling (verified)
A pre-existing user config whose ENTIRE non-comment content is a degenerate empty-root token (`{}`, `null`, or `~`) would yield invalid YAML when a block-mapping key is appended (`{}\neditor: nvim` → parse error). Truly-empty files and comment-only files are already safe. The fix adds `_strip_degenerate_root()` to the surgical edit path: it detects a lone empty-root token and drops it before appending, so the key becomes the document's root mapping. Verified via `63-edge-case-probe.py` across all five shapes (empty, `{}`, `null`, `~`, comment-only). The existing unit suite exercises a `{}`-content config (`test_get_setting_respects_caller_default_at_call_site`), so the regression test MUST include a `set_setting` against a `{}`-content file.

### Systemic Audit (Phase 4)

**Root-cause category:** lossy round-trip mutation of a user-editable document through a data-only loader (`yaml.safe_load` → `yaml.dump`).

**Categorical census (`git grep` of all write sites in `src/`):**

| Write site | Target file | Classification |
| --- | --- | --- |
| `yaml_config_adapter.py:142` (`yaml.dump`) | `.teddy/config.yaml` | **User-editable — the defect** |
| `prompt_manager.py:145` (`yaml.dump`) | turn meta | Machine-owned (lossy OK) |
| `session_repository.py:132` (`yaml.dump`) | session meta | Machine-owned (lossy OK) |
| `openrouter_hydrator.py:104` (`json.dumps`) | model cache | Machine-owned cache |
| `context_service.py:448` (`json.dumps`) | web-content cache | Machine-owned cache |
| `update_checker.py:194` (`json.dumps`) | update cache | Machine-owned cache |

`config.yaml` is the ONLY user-editable file round-tripped, so no additional `Refactor` deliverable is spawned. The preventative rule ("mutate user-editable files surgically, never via a data-only round-trip") applies to exactly this one site today.

**Call-site census (`git grep set_setting`):** the only production caller is `session_cli_handlers.py:573` with key `"editor"` (plus the Port declaration in `config_service.py:32`). The fix's behavioural surface is therefore bounded to the `editor` key.

**Impact Audit:** `IConfigService.set_setting(key, value)` keeps its exact signature — no Port/Signature/DTO change — so no Contract→Migration→Cleanup partition is required, and the preflight reword is a single untested string site (Turn 11 census). No matching Harness deliverable is needed.

### Secondary Change (user-requested, confirmed)
Reword the editor preflight message in `session_cli_handlers._validate_editor_config()` from "No editor configured. Scanning for available editors in PATH..." to **"No editor configured. Please select one below:"** (confirmed by the user). The neutral wording avoids the inaccuracy of "found in PATH" when discovery subsequently finds nothing.
