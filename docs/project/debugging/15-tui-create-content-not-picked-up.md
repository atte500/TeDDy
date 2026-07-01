# Bug: TUI CREATE Action Content Not Picked Up
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When executing an action using 'x' in the TUI (Textual Plan Reviewer), changes made to the contents are not picked up. This was tested on CREATE actions but might also affect EDIT actions.

Expected: Modified content in the TUI is used when the action is executed.
Actual: The original (unmodified) content is used instead.

## Context & Scope
### Regressing Delta
This is not a regression but a design omission. `harvest_action_content()` was implemented to transfer modified content from `pending_temp_file` back into `action.params`, but it was only wired into `action_submit()` and `action_cancel()` — NOT into the execution path (`action_execute_step` → `orchestrate_execution()`). The function has existed since the TUI execution module was implemented, but the call was never added to the execution path.

### Environmental Triggers
- TUI mode (Textual Plan Reviewer)
- Action type: CREATE (and potentially EXECUTE, RESEARCH which also use `pending_temp_file` via `preview_text_action()`)
- Using 'x' key to execute an action after modifying content via external editor ('e' key)
- External editor must have been launched (content written to `pending_temp_file`) and modifications confirmed before pressing 'x'

### Ruled Out
- EDIT actions: These modify `action.params["edits"]` directly in `preview_edit()` via `harvest_edit_diff()`, so they are NOT affected by this bug.
- READ actions: These are read-only and don't use `pending_temp_file` for the harvest pattern.
- The `action_submit()` path: Works correctly because it calls `_harvest_action_content()` before returning the plan.
- The `action_cancel()` path: Cleans up temp files but this doesn't require content harvest.

## Diagnostic Analysis
### Causal Model
The TUI execution flow for 'x' (execute_step) is:
1. `ReviewerApp.action_execute_step()` → calls `execute_step_logic()` in logic module
2. `execute_step_logic()` → calls `exec_logic()` (alias for `execute_step_logic` in execution module)
3. `exec_logic()` → `orchestrate_execution()` → `_execute_silently()` → `dispatcher.dispatch_and_execute(action)`

The `orchestrate_execution()` function passes the `action` object directly to the dispatcher. But the action's `params` dict still contains the ORIGINAL content from parsing. The `harvest_action_content()` function is only called in `action_submit()` and `action_cancel()` — NOT in the execution path.

This means when 'x' is pressed, the action is executed with its original `params["content"]` value, ignoring any modifications made via the external editor (which writes to `action.pending_temp_file`).

The fix: Add a call to `harvest_action_content(action, app.INSTRUCTION_MARKER)` at the start of `orchestrate_execution()` in `textual_plan_reviewer_execution.py`, before the action is dispatched.

### Discrepancies
None — the causal model has been empirically verified by the MRE.

### Investigation History
1. Static analysis of TUI execution flow. The `harvest_action_content()` call is missing from the execution path. The function is only called in `action_submit()` and `action_cancel()`. Confirmed by grep search.
2. MRE execution. Simulated a CREATE action with original content, wrote modified content to a temp file, set `pending_temp_file`, and demonstrated that `params["content"]` remains "original content" while `pending_temp_file` contains "modified content". Then called `harvest_action_content()` and confirmed it correctly updates `params["content"]`. This proves the root cause — the harvest call is missing from `orchestrate_execution()`.

## Solution
**Root Cause:** The `harvest_action_content()` function was designed to transfer modified content from `action.pending_temp_file` back into `action.params` after external editor editing. However, it was only wired into `action_submit()` and `action_cancel()` — it was never called in the execution path (`orchestrate_execution()`). When a user pressed `x` to execute a CREATE, EXECUTE, or RESEARCH action after modifying its content via the editor (`e` key), the action was dispatched with the original `params` values, ignoring the modified content in `pending_temp_file`.

**Fix:** Added a single line to `orchestrate_execution()` in `textual_plan_reviewer_execution.py`:
```python
harvest_action_content(action, app.INSTRUCTION_MARKER)
```
This is placed immediately after setting the action's state to RUNNING, before dispatching to `_execute_silently()`. It ensures that any content modified via the external editor is harvested back into `action.params` before the action is executed.

**Preventative Measures:**
- The fix is localized to the execution orchestration function, making it visible and auditable.
- Regression test `test_tui_content_harvest.py` covers all three affected action types (CREATE, EXECUTE, RESEARCH) and verifies that unaffected types (EDIT) are not modified.

**Scope:**
- Affected actions: CREATE (`params["content"]`), EXECUTE (`params["command"]`), RESEARCH (`params["queries"]`).
- Not affected: EDIT (modifies `params["edits"]` directly via `harvest_edit_diff()`), READ (read-only, no temp file pattern).
