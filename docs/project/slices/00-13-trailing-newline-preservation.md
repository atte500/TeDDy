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
3. Downstream `ActionChangeSetBuilder`, `ActionExecutor`, `validation_rules/edit`, `EditSimulator`: no code change; confirmed by full suite remaining green.

## Deliverables

- [x] **Core** - Preserve authored trailing newlines in CREATE content. Remove `.rstrip("\n")` at `action_parser_strategies.py:53` (take `child.content` verbatim). Migrate CREATE assertions: `test_parser_basic_actions.py` (`test_parse_create_action`, `test_parser_succeeds_on_builder_generated_create_action`), `test_parser_fence_cleanup.py` (both closing-fence tests), `test_parser_misc.py` (nested-fence test). Each migrated expectation equals the current value plus its authored trailing newline(s).
- [ ] **Core** - Preserve authored trailing newlines in EDIT FIND/REPLACE. Remove `.rstrip("\n")` at `action_parser_complex.py:36/54` (take `get_child_text(...)` verbatim). Migrate EDIT assertions: `test_parser_basic_actions.py` (`test_parse_edit_action`, `test_parse_edit_action_preserves_indentation_in_find_and_replace` including the false mistletoe-strips comments, `test_parse_edit_action_ignores_find_in_codeblock`) and `test_parser_crlf_normalization.py` (EDIT test; MESSAGE test unaffected).

## Implementation Notes

### Deliverable 1 (CREATE preservation)
- Removed `.rstrip("\n")` from the CREATE content assignment at `action_parser_strategies.py:53`; `params["content"]` now takes `child.content` verbatim, matching the proven replica.
- Migrated five CREATE parser assertions to the verbatim value (current parsed content plus its authored trailing newline): `test_parser_basic_actions.py` (`test_parse_create_action`, `test_parser_succeeds_on_builder_generated_create_action`), `test_parser_fence_cleanup.py` (both closing-fence tests), and `test_parser_misc.py` (the nested-fence test, whose expected literal was restructured to append the authored `\n`).
- Red proved the strip was the sole cause (`actual == expected` minus the trailing `\n`); Green flipped all five to pass (`12 passed` across the three modules).
- Integration surfaced one Local Flaw: `test_create_overwrite_integration.py` asserted the pre-fix stripped bytes. Migrated the side-effect assertion to `"new content\n"`, because `MarkdownPlanBuilder` always emits a trailing newline before the closing fence. Full `make test` green afterward (2164 passed, 5 skipped).

## Verification
1. **CREATE trailing newline persisted:**
   Create a plan file whose CREATE fence ends with a blank line before the closing fence, run `uv run teddy execute <plan-file>` and approve the action, then run `od -c <created-file>`.
   Verify the output ends with two newline escapes (`\n \n`).
2. **EDIT trailing newline persisted:**
   Prepare a target file, then run an EDIT plan whose REPLACE block ends with a blank line and approve it.
   Verify the edited file ends with the authored blank line using `od -c <edited-file>`.
