# Slice: Preserve Authored Trailing Newlines in CREATE and EDIT Fence Content
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** [Fixed sandbox replica](../../../spikes/debug/trailing-newline-deletion/02-replica-fixed-verification.py)
- **Component Docs:** [MarkdownPlanParser](../../architecture/core/services/markdown_plan_parser.md), [ActionParserStrategies](../../architecture/core/services/action_parser_strategies.md), [EditSimulator](../../architecture/core/services/edit_simulator.md)
- **Scope Slug:** `newline-preservation`

## Goal
Persist CREATE and EDIT fence content exactly as authored, including author-chosen trailing newlines and blank lines, so a CREATE file ends with the authored blank line and an EDIT REPLACE block keeps its trailing newline(s). Reference: [Bug 76](../debugging/76-trailing-newline-deletion.md).

## Context
The plan parser strips author-chosen trailing newlines from CREATE content and EDIT FIND/REPLACE blocks, so authored blank lines vanish before the verbatim file adapter writes them.

- `MarkdownPlanParser`: sole upstream caller; dispatches CREATE to `parse_create_action` and EDIT to `parse_edit_action` (`markdown_plan_parser.py` dispatch map). No change required.
- `parse_create_action`: `params["content"] = child.content.rstrip("\n")` at `action_parser_strategies.py:53` deletes authored trailing newlines. Removing the strip takes `child.content` verbatim.
- `parse_edit_action`: `get_child_text(find_code).rstrip("\n")` at `action_parser_complex.py:36` and `get_child_text(replace_code).rstrip("\n")` at `:54` delete authored trailing newlines.
- `parse_message_action`: `raw_content.rstrip("\n")` at `action_parser_complex.py:207` is the MESSAGE path and is intentionally out of scope.
- `mistletoe`: returns the literal bytes between fence lines including the final line terminator (a fence ending in a text line yields `'abc\n'`; one authored blank line yields `'abc\n\n'`). The strip therefore deletes real content. Proved end-to-end by the sandbox replica.
- `EditSimulator`: additive-newline branch is guarded by `not find.endswith("\n") and not replace.endswith("\n")`, so it becomes inert once FIND/REPLACE carry their authored trailing newlines; `EditMatcher` newline-indifference covers files lacking a trailing newline.
- `LocalFileSystemAdapter`: writes with `newline=""` and performs no stripping, so the loss is entirely attributable to the parse-time strip.
- `ActionChangeSetBuilder`, `ActionExecutor`, `validation_rules/edit`: read `content`/`edits` without terminal-newline assumptions; diffs will now show trailing-newline additions.

No Wiring deliverable: the parser is already wired end-to-end (`MarkdownPlanParser` → `ActionChangeSetBuilder` → `Executor` → `LocalFileSystemAdapter`) and this is a leaf-behavior correction with no new layers to connect. The bug doc's replica script is the end-to-end proof; existing unit and integration suites cover the downstream path.

Verbatim rule: the fixed content equals the current parsed content plus the authored trailing newline(s) that the strip currently removes.

## Scenarios
Primary user journeys; regression targets for the end-to-end behavior.

> As a plan author, I want authored trailing newlines preserved so that generated files keep their trailing blank lines.

```gherkin
Given a CREATE action whose fence content ends with a blank line before the closing fence
When the plan is parsed and executed
Then the written file ends with the authored blank line

Given an EDIT action whose REPLACE block ends with a trailing newline
When the plan is parsed and executed
Then the edited file keeps that trailing newline
```

## Edge Cases
- **CREATE plain:** If the fence content ends with the last text line (one trailing terminator), then `params["content"]` ends with exactly one `\n`.
- **CREATE blank line:** If the fence content has one authored blank line before the closing fence, then `params["content"]` ends with two `\n`.
- **CREATE empty:** If the fence has no children, then `params["content"]` stays `""` (no change).
- **CREATE nested fence:** If the fence content itself contains a shorter nested fence, then the verbatim content ends with the authored terminator after the inner closing fence.
- **EDIT FIND/REPLACE:** If FIND or REPLACE block ends with a trailing newline, then the parsed `find`/`replace` keep it verbatim.
- **CRLF plan:** If the plan carries CRLF line endings, then normalization to LF happens first and the verbatim content ends with LF only.
- **MESSAGE unaffected:** If a MESSAGE action is parsed, then its content is still `rstrip("\n")`-trimmed (out of scope).

## Key Unknowns
None. The bug doc proves the fix in an isolated sandbox replica and re-verifies downstream consumers via static reading.

## Impact
1. `[MIGRATE]` `parse_create_action` — Remove `.rstrip("\n")` at `action_parser_strategies.py:53`; migrate CREATE parser tests to assert verbatim content.
2. `[MIGRATE]` `parse_find_replace_pair` — Remove `.rstrip("\n")` at `action_parser_complex.py:36/54`; migrate EDIT parser tests and correct the false mistletoe-strips comments.
3. Downstream `ActionChangeSetBuilder`, `ActionExecutor`, `validation_rules/edit`: no code change. `EditSimulator`/`edit_matcher` DO require a change: verbatim trailing newlines break intra-line substring replacement (see Implementation Notes). This is handled by the prepended matcher newline-consistency deliverable, before the EDIT parser change.

## Deliverables

- [x] **Core** - Preserve authored trailing newlines in CREATE content. Remove `.rstrip("\n")` at `action_parser_strategies.py:53` (take `child.content` verbatim). Migrate CREATE assertions: `test_parser_basic_actions.py` (`test_parse_create_action`, `test_parser_succeeds_on_builder_generated_create_action`), `test_parser_fence_cleanup.py` (both closing-fence tests), `test_parser_misc.py` (nested-fence test). Each migrated expectation equals the current value plus its authored trailing newline(s).
- [x] **Core** - Make EDIT matching newline-consistent for verbatim FIND/REPLACE blocks. Preserving authored newlines (next deliverable) makes a single-line FIND block carry a trailing `\n` (e.g. `DEBUG:\n`); the matcher's intra-line substring boost strips that newline from the matched region but not from the REPLACE, so `str.replace` injects newlines mid-line (`Hello, TeDDy\n!`, `INFO:\n start`). In `EditSimulator`/`edit_matcher`, align the REPLACE terminal newline with the matched region: strip it when the match is an intra-line fragment that dropped the newline; keep the existing additive behaviour when the match spans a full file line but the REPLACE lacks a newline; preserve authored newlines when the match spans full lines. Drive with unit tests that pass trailing-newline FIND/REPLACE directly to the simulator (the parser still strips, so the existing suites stay green).
- [x] **Core** - Preserve authored trailing newlines in EDIT FIND/REPLACE. Remove `.rstrip("\n")` at `action_parser_complex.py:36/54` (take `get_child_text(...)` verbatim). Migrate EDIT assertions: `test_parser_basic_actions.py` (`test_parse_edit_action`, `test_parse_edit_action_preserves_indentation_in_find_and_replace` including the false mistletoe-strips comments, `test_parse_edit_action_ignores_find_in_codeblock`) and `test_parser_crlf_normalization.py` (EDIT test; MESSAGE test unaffected). Also migrate the acceptance expectations whose shape shifts with verbatim newlines: `test_edit_ux_polish.py` (`test_multi_edit_ux_polish` score and diff), `test_similarity_threshold_config.py` (`test_respects_global_similarity_threshold` score), and `test_validator_edit.py` (`test_validate_edit_fails_if_find_block_not_unique` FIND shape).

## Implementation Notes

### Systemic regression discovery (blocks EDIT preservation)
The EDIT parser deliverable was implemented and its four parser-level assertions passed (8 passed in isolation), but the full `make test` gate surfaced six failures. Classification: **Systemic Regression**. Preserving trailing newlines makes a single-line FIND block carry an authored `\n` (e.g. `"DEBUG:\n"`). The fuzzy matcher's intra-line substring boost strips that newline from the matched region but not from the REPLACE, so `str.replace("DEBUG:", "INFO:\n")` injects newlines mid-line (`"INFO:\n start"`, `"Hello, TeDDy\n!"`), corrupting files. Similarity scores also shifted (`0.81→0.86`, `0.82→0.84`) and uniqueness detection changed shape, both the same cause. The bug doc's assumption that `EditSimulator` stays inert and `EditMatcher` newline-indifference covers this was falsified: fixing it needs production changes in `edit_simulator.py`/`edit_matcher.py`, outside the EDIT parser deliverable. The failure affects real users, not only the builder, because a real fence always has a newline before its closing line. Per Systemic Recovery, the uncommitted EDIT work was discarded back to `36b942ae` and a `Core` prerequisite deliverable was prepended to make matching newline-consistent.

### Deliverable 1 (CREATE preservation)
- Removed `.rstrip("\n")` from the CREATE content assignment at `action_parser_strategies.py:53`; `params["content"]` now takes `child.content` verbatim, matching the proven replica.
- Migrated five CREATE parser assertions to the verbatim value (current parsed content plus its authored trailing newline): `test_parser_basic_actions.py` (`test_parse_create_action`, `test_parser_succeeds_on_builder_generated_create_action`), `test_parser_fence_cleanup.py` (both closing-fence tests), and `test_parser_misc.py` (the nested-fence test, whose expected literal was restructured to append the authored `\n`).
- Red proved the strip was the sole cause (`actual == expected` minus the trailing `\n`); Green flipped all five to pass (`12 passed` across the three modules).
- Integration surfaced one Local Flaw: `test_create_overwrite_integration.py` asserted the pre-fix stripped bytes. Migrated the side-effect assertion to `"new content\n"`, because `MarkdownPlanBuilder` always emits a trailing newline before the closing fence. Full `make test` green afterward (2164 passed, 5 skipped).

### Prerequisite (matcher newline consistency)
- Added an inverse alignment branch to `EditSimulator._apply_single_edit`, mirroring the existing additive branch: when `find.endswith("\n")` but `best_match` does not (an intra-line fragment match dropped the terminator) and `replace.endswith("\n")`, the authored REPLACE terminator is stripped (CRLF-aware) so `str.replace` cannot inject it mid-line.
- The fix lives in `edit_simulator.py` only; `edit_matcher.py` is unchanged. The score shifts (`0.81→0.86`, `0.82→0.84`) and the uniqueness-detection change are parser-deliverable test migrations, not matcher bugs. `test_validate_edit_fails_if_find_block_not_unique` builds a FIND with a trailing `\n` that the builder then doubles into a blank-line block, which the matcher correctly reports as unique.
- Red (turn 30): the two fragment cases failed (`'Hello, TeDDy\n!'`, `'INFO:\n start...'`) while the CRLF/LF guards and the full-line preservation guard passed (`2 failed, 3 passed`). Green (turn 31): `5 passed`.
- Integration (turn 32): full `make test` green (2167 passed, 5 skipped). The branch is inert while the parser still strips, so no existing suite changed.

### Deliverable 3 (EDIT parser preservation)
- Removed `.rstrip("\n")` from both EDIT assignments in `action_parser_complex.py`: `find_content = get_child_text(find_code)` (line 36) and `replace_content = get_child_text(replace_code)` (line 54). Fence content is now taken verbatim, matching the proven replica.
- The MESSAGE path at `action_parser_complex.py:207` still calls `raw_content.rstrip("\n")`; it is intentionally out of scope because MESSAGE content is rendered, not persisted verbatim.
- Red (turn 37): migrated four EDIT parser assertions to the verbatim shape (`find`/`replace` equal the previously-stripped value plus the authored trailing `\n`); result `4 failed, 4 passed`.
- Green (turn 38): removing the two strips flipped all four to pass; `8 passed` on the parser modules.
- Integration (turn 39): full `make test` surfaced three Local-Flaw test migrations driven purely by the parsed block now carrying its authored newline (the matcher was unchanged): `test_multi_edit_ux_polish` score `0.81 → 0.86`, `test_respects_global_similarity_threshold` score `0.82 → 0.84`, and `test_validate_edit_fails_if_find_block_not_unique` where the builder's trailing-`\n` find doubled into a blank-line block the matcher correctly reports as unique. Local Recovery (turn 41) migrated all three; full `make test` green (`2167 passed, 5 skipped`).
- Corrected the false mistletoe-strips premise in `test_parser_basic_actions.py`: fence content is verbatim; the f-string template authors one blank line before the closing fence, so the parsed block carries an extra `\n`.

## Verification
1. **CREATE trailing newline persisted:**
   Create a plan file whose CREATE fence ends with a blank line before the closing fence, run `uv run teddy execute <plan-file>` and approve the action, then run `od -c <created-file>`.
   Verify the output ends with two newline escapes (`\n \n`).
2. **EDIT trailing newline persisted:**
   Prepare a target file, then run an EDIT plan whose REPLACE block ends with a blank line and approve it.
   Verify the edited file ends with the authored blank line using `od -c <edited-file>`.
