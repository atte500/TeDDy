# Bug: TUI Multi-Bug Fixes
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
1. Right panel: `e` should edit the selected param (currently requires `ENTER`).
2. Editing RESEARCH action crashes with `AttributeError: 'list' object has no attribute 'translate'` because `ParameterEditModal` receives a list for `initial_value`.
3. PROMPT action: missing original contents and editor context line. Message param shows "None", preview is empty. Should parse both message and reply.
4. `e` on READ action causes deadlock/garbling (similar to previous editor freeze).
5. Event log shows weird formatting due to concurrency issues.
6. EXECUTE: modifying the main action via `e` does not reflect the changes on the right panel parameter.
7. READ action: executing via `x` doesn't instantly show the log on the right (requires focus toggle) and freezes the TUI due to large text size.

## System Model
**Understanding:**
1. **Right Panel `e` Binding:** The `ParameterDetail` (`ListView`) only listens to the native `ListView.Selected` event (Enter key). It lacks an action or key binding mapped to the `e` key.
2. **RESEARCH Crash:** In `textual_plan_reviewer_logic.py:edit_action_logic`, the `val` for `RESEARCH` is a list, but it is passed directly to `ParameterEditModal("Queries:", val)` which expects a string.
3. **PROMPT Parsing:** `preview_prompt` in `textual_plan_reviewer_previews.py` only seeds the editor with `action.params.get("message", "")`. It does not include the standard reply instruction markers or the context that the console executor uses.
4. **READ Deadlock:** `preview_readonly` uses `await anyio.to_thread.run_sync(app._system_env.run_command, editor_cmd + [temp_file])`. `run_command` likely captures stdout/stderr synchronously and corrupts the terminal state when an interactive editor like `vim` or `nano` takes over, rather than using `subprocess.Popen` directly as `launch_editor` does.
5. **Event Log Formatting:** The previous event log was replaced by a `StatusBar` widget, but asynchronous background tasks writing to it might still cause interleaving or the execution log details in the right pane are overlapping.
6. **Main Action State Reactivity:** Edits via `e` inside `edit_action_logic` mutate the action parameters and call `app._refresh_node(node)`, but do not explicitly call `_update_detail_view(app, action)` to refresh the right pane.
7. **READ Freeze:** Rendering large execution logs in the right pane uses `ListItem(Label(f"[bold]details:[/] {log.details}"))`. Large `details` strings freeze the Textual layout engine because `Label` is not optimized for large text blocks; a `TextArea` or `RichLog` must be used instead.

**Conflicts:**

## Solution
**Implemented:**
- `textual_plan_reviewer_app.py`: Updated `action_edit_details` to prioritize right-pane focus for parameter editing.
- `textual_plan_reviewer_logic.py`:
  - RESEARCH editing casts list to pipe-separated string and parses it back.
  - Added calls to `_update_detail_view(app, action)` when editing `EXECUTE` and `RESEARCH` parameters to guarantee reactivity.
  - Removed the inline log rendering block from `_update_detail_view` completely to provide a cleaner UI focus on parameters.
- `textual_plan_reviewer_previews.py`:
  - Added `with app.suspend():` context block when running `preview_readonly` to prevent terminal corruption.
  - Injected `<!-- Please enter your response above this line. -->` template structure into `preview_prompt` to match `console_plan_reviewer.py` formatting and UX.
- `textual_plan_reviewer_helpers.py`: Fixed `resolve_action_parameters` dictionary keys to match string `action.type` directly (fixing `None` values) and explicitly appended the `user_response` value for PROMPT actions.

**Prevention & Generalization:**
- **State Reversion Resilience:** Replaced `copy.deepcopy` with safe, shallow `dict.copy()` to handle AST-polluted parsed properties without crashing when users trigger `r` (Revert).
- **UI Reactivity Standardization:** Enforced explicit `_update_detail_view` synchronizations on all state-mutating actions across the TUI logic (`EXECUTE`, `RESEARCH` modals, and `revert`) so the right panel never shows stale data.
- **Strict I/O Isolation:** Wrapped background text-rendering tools in `contextlib.redirect_stdout` and interactive editors in `app.suspend()` to guarantee TUI layout integrity and prevent execution output garbling.
- **Formal Regression Suite:** Created `tests/suites/unit/adapters/inbound/test_tui_regressions.py` directly mapping the 7 observed real-world edge cases (READ deadlock, list crashes, prompt mapping, overlapping logs, and UI reactivity) to automated tests. This prevents future drifts and strictly validates the TUI-to-Parser interactions.
