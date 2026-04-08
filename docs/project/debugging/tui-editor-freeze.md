# Bug: TUI Freezes and Garbles Text on Edit of CREATE Action
- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When using the interactive TUI, pressing `e` (edit), `v` (view), or `m` (modify) on a `CREATE` action opens the content in a temporary file (e.g., in VSCode). However, the TUI then becomes unresponsive and displays garbled text. Upon saving and exiting the editor, the TUI remains frozen or fails to register the changes when submitting the plan. Conversely, pressing `e` on an `EDIT` action opens a side-by-side diff properly and successfully asks for confirmation, capturing the changes.

## System Model
**Understanding:**
The freeze and garbled text occur because the TUI violates the "Non-Blocking Deferred Harvest" pattern. Specifically, `launch_editor` in `textual_plan_reviewer_previews.py` attempts to use `with app.suspend():` and blocking `run_sync` calls to halt the TUI until the editor closes. In an async Textual context (especially when invoked from `@work` decorated action handlers), mixing `app.suspend()` with concurrent event loops or missing confirmation modals causes terminal deadlocks and visual corruption.

The reason `EDIT` works is that it detects a `diff_viewer` command (which most systems have configured) and bypasses `launch_editor` entirely, running the diff command in a background thread while immediately pushing a `ConfirmScreen` overlay to manage the suspension manually. `CREATE` directly awaits `launch_editor` without a confirmation modal, triggering the deadlock.

**Conflicts:**
-

## Solution
**Implemented:**
- **Deferred Harvest Pattern:** Refactored `launch_editor` and `_preview_edit_diff_viewer` in `textual_plan_reviewer_previews.py` to replace `app.suspend()` and blocking `run_command` calls with asynchronous detached `subprocess.Popen` execution.
- **TUI Synchronization:** Added explicit `ConfirmScreen` overlays ("Save manual changes? (y/n)") to pause the TUI logical flow, harvesting the temporary file *only* upon user confirmation.
- **Test Harness Insulation:** Integrated an `app.is_headless` check to bypass the `ConfirmScreen` overlays during headless acceptance tests, preventing `Pilot` hangs while perfectly simulating immediate user mock confirmations.
