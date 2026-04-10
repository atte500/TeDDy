# Bug: TUI UX and Action Handling Regressions

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [10-09-advanced-tui-ux-polish](../../slices/00-04-tui-ux-polish-refinements.md)
- **Specs:** [interactive-session-workflow](../../specs/interactive-session-workflow.md)

## Symptoms

The TUI exhibits several functional and UX regressions:
1. **PROMPT Action:**
    - Desync between right panel and editor.
    - Prompt message incorrectly persists if edited.
    - Response parsing includes the instruction comment `<!-- Please enter your response above this line. -->`.
2. **Action Logging:** The log for an action does not appear in the right panel when executed via the `x` shortcut.
3. **Navigation:** `Left`/`Right` arrow keys do not switch focus between the Action Tree and the Detail Panel.
4. **Notifications:** Toast notifications still appear during/after action execution.
5. **RESEARCH Action:**
    - Queries cannot be edited from the right panel.
    - Queries are represented as a pipe-delimited string (`query1 | query2`) in the editor instead of a clean format.
6. **EDIT Action:** The `before` side of the diff is editable during modification, which is unsafe.

## System Model

### Understanding
The TUI uses a hybrid interaction model:
1. **Deferred Harvest:** Content for `CREATE`, `PROMPT`, `EXECUTE`, and `RESEARCH` is managed via persistent temp files and harvested on submission or execution.
2. **Inline Editing:** Simple parameters (paths, flags) are edited via modals triggered from the `ParameterDetail` (right) pane.

Root Causes identified:
1. **PROMPT Desync:** `ReviewerApp` and `preview_prompt` use different instruction markers and different sanitization logic. `preview_prompt` fails to load existing `user_response`.
2. **Missing Logs:** `resolve_action_parameters` (helpers.py) is hardcoded to only show base parameters, omitting the `ActionLog` payload.
3. **Arrow Navigation:** `BINDINGS` in `ReviewerApp` lacks arrow key mappings.
4. **Notifications:** Toast notifications are triggered by `ActionExecutor` calling the `UserInteractor.notify_skipped_action` or similar, which in TUI mode might be bridged to `app.notify`.
5. **RESEARCH Brittleness:** `edit_action_logic` (logic.py) uses a pipe-split string for list parameters, and `on_list_view_selected_logic` blocks list editing via a type check.
6. **EDIT Safety:** `preview_edit` (previews.py) creates a writable "before" file for diffing.

### Discrepancies
None. All reported symptoms are mapped to specific code locations and logic flaws.

## Solution

### Implemented Fixes
- **PROMPT Logic:** Unified `INSTRUCTION_MARKER`, implemented response loading in previews, and added marker-stripping sanitization to the harvest logic.
- **Action Logs:** Updated `resolve_action_parameters` to include `ActionLog` fields (status, details, failed_command) after execution.
- **Navigation:** Added `left`/`right` arrow key bindings for pane-to-pane focus switching.
- **Notifications:** Silenced the `ActionDispatcher` info logs in the TUI's `execute_step_logic` to prevent logs from being captured as notifications.
- **RESEARCH Logic:** Enabled list editing for `queries` in the detail view and replaced pipe-splitting with comma-splitting in the modal.
- **EDIT Safety:** Implemented `os.chmod` (read-only) on the "before" side of diffs and for `READ`/`PRUNE` previews.

### Prevention
- Added `test_tui_ux_regressions.py` to verify the sanitization logic and list parsing.
