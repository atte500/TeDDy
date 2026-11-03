# Bug: Trailing Newlines Deleted from EDIT and CREATE Content
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Expected: content authored inside a CREATE code fence or an EDIT FIND/REPLACE block is persisted exactly as written, including author-chosen trailing newline(s). A CREATE whose fence content ends with a blank line should produce a file ending with a blank line; an EDIT replacement block ending with a newline should persist that newline.

Actual: the parsed action parameters arrive with trailing newlines removed, so the written file loses them. The `LocalFileSystemAdapter` write path is verbatim (`newline=""`), so the loss happens before the adapter is reached.

## Context & Scope
### Regressing Delta
The trailing-newline deletion is introduced by two `rstrip("\n")` calls in the plan parse layer:
- `src/teddy_executor/core/services/action_parser_strategies.py:53` — `params["content"] = child.content.rstrip("\n")` (CREATE content), introduced by commit `893ea3c9a` (2026-02-26).
- `src/teddy_executor/core/services/action_parser_complex.py:36` and `:54` — `get_child_text(find_code).rstrip("\n")` / `get_child_text(replace_code).rstrip("\n")` (EDIT FIND/REPLACE), introduced by commit `b0f9943d5` (2026-03-13).

Both calls compensate for a stripping behavior that `mistletoe` does not exhibit (see Causal Model).

### Environmental Triggers
Any OS. The plan parsing path (`MarkdownPlanParser` and its action strategies) is always in play for CREATE and EDIT actions.

### Ruled Out
- `LocalFileSystemAdapter` write path: `create_file`, `write_file`, and `edit_file` all pass `newline=""` and perform no `rstrip`. Verified in Turn 1.
- `EditSimulator`: only additive newline alignment; performs no trailing-newline stripping. Verified in Turn 1.

## Diagnostic Analysis
### Causal Model
`mistletoe` returns the literal bytes between fence lines, INCLUDING the final line's terminator (verified: a fence with content `abc` yields `'abc\n'`; an authored blank line yields `'abc\n\n'`). The plan parser therefore already receives the author's exact trailing newlines. The `rstrip("\n")` calls then delete those authored newlines before they reach the adapter, so CREATE persists a file without its trailing newline and EDIT persists a replacement without its trailing newline(s). The `LocalFileSystemAdapter` writes verbatim (`newline=""`), so the loss is entirely attributable to the parse-time strip. The false premise that "the AST parser strips the trailing newline from a code block" is also encoded in test comments (`test_parser_basic_actions.py:150/203`), which accommodate the strip rather than assert authored content.

### Discrepancies
- [x] Trailing newlines authored in CREATE/EDIT blocks are removed before the adapter writes the file (Resolved: `rstrip("\n")` at `action_parser_strategies.py:53` and `action_parser_complex.py:36/54`; removing it in the sandbox replica preserves authored newlines end-to-end).
- [x] The outbound file-write adapter is newline-deterministic (Resolved: `newline=""` disables platform translation and no rstrip is applied).
- [x] The plan parser's `rstrip("\n")` compensates for a `mistletoe` stripping behavior that does not exist (Resolved: probe showed `mistletoe` returns fence content verbatim, including the trailing newline).

### Investigation History
1. Investigated the outbound file-write adapter by reading `local_file_system_adapter.py`; observed no trailing-newline stripping and `newline=""` on every write, which eliminated the adapter as the deletion site.
2. Searched `src/` for `.rstrip`/`.strip` near content extraction; observed `rstrip("\n")` calls in `action_parser_strategies.py` (CREATE) and `action_parser_complex.py` (EDIT find/replace), which narrowed the deletion site to the plan parser.
3. Probed `mistletoe` `CodeFence` content extraction; observed fence content `'abc\n'` and `'abc\n\n'`, proving `mistletoe` preserves authored trailing newlines, so `rstrip("\n")` is the deletion site.
4. Ran the production-path MRE (`spikes/debug/trailing-newline-deletion/01-create-edit-newline-mre.py`); observed CREATE_PLAIN and CREATE_BLANK both persist `b'line1\nline2'` and EDIT parses `find='old'`/`replace='new'`, reproducing the symptom end-to-end.
5. Blamed the strip lines: `893ea3c9a` (CREATE) and `b0f9943d5` (EDIT); inspected `test_parser_basic_actions.py` and found test comments that falsely blame `mistletoe`, confirming the tests encode the mis-implementation.
6. Built fixed sandbox replicas (`replica_action_parser_strategies.py`, `replica_action_parser_complex.py`) and ran `spikes/debug/trailing-newline-deletion/02-replica-fixed-verification.py`; observed fixed CREATE persists `b'line1\nline2\n'` and `b'line1\nline2\n\n'`, fixed EDIT parses `find='old\n'`/`replace='new\n\n'` and persists `b'new\n\n'` — all assertions passed.
7. Audited blast radius: the sole upstream caller is the `MarkdownPlanParser` dispatch map; downstream consumers are `action_changeset_builder.py`, `action_executor.py`, `validation_rules/edit.py`, and `validation_rules/message.py`; the `EditSimulator` additive-newline branch becomes inert for the fixed shape.

## Solution
### Root Cause
Verified: the plan parse layer strips author-chosen trailing newlines from CREATE content and EDIT FIND/REPLACE blocks via `rstrip("\n")` (`action_parser_strategies.py:53`, `action_parser_complex.py:36/54`). `mistletoe` already preserves the authored newlines, so the strip deletes real content. Removing the strip (proven in the sandbox replica at `spikes/debug/trailing-newline-deletion/02-replica-fixed-verification.py`) makes CREATE and EDIT persist fence content verbatim. The fix was proven in the sandbox replica, NOT applied to `src/`. It touches TWO production files plus their parser tests, exceeding the small-change bar, so it is a Developer handoff (see Affected Components).

### Affected Components
- `src/teddy_executor/core/services/action_parser_strategies.py`: remove `.rstrip("\n")` from the CREATE content assignment (line 53); take `child.content` verbatim.
- `src/teddy_executor/core/services/action_parser_complex.py`: remove `.rstrip("\n")` from the EDIT FIND (line 36) and REPLACE (line 54) assignments; take `get_child_text(...)` verbatim.
- `src/teddy_executor/core/services/markdown_plan_parser.py`: sole upstream caller (dispatch map at lines 52/54); no change required.
- `src/teddy_executor/core/services/edit_simulator.py`: the additive-newline branch (lines 51-60, guarded by `not find.endswith("\n") and not replace.endswith("\n")`) becomes inert for the fixed shape; verify single-edit behavior on files that lack a trailing newline (the `EditMatcher` newline-indifference already covers the mismatch).
- `src/teddy_executor/core/services/action_changeset_builder.py`: reads `content`/`edits` (lines 78/83); diffs will now show trailing-newline additions — confirm no diff assumption breaks.
- `src/teddy_executor/core/services/action_executor.py` (reads `content`, line 141) and `src/teddy_executor/core/services/validation_rules/edit.py` (reads `edits`, line 83): re-verify no shape assumptions. `validation_rules/message.py` reads MESSAGE `content` and is unaffected.
- Tests to update: `tests/suites/unit/core/services/test_parser_basic_actions.py` (drop the `.rstrip("\n")` expectations at lines 205-206 and correct the mistletoe-strips comments at lines 150/203), plus `test_parser_crlf_normalization.py`, `test_parser_fence_cleanup.py`, and any acceptance/inbound tests asserting stripped content.
