# Bug: Windows TUI Worker Crash during Edit Workflow

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
In Windows CI, `test_tui_modifying_edit_action_content_succeeds` causes the `pytest-xdist` worker to crash with `node down: Not properly terminated`.
- **Expected:** Test passes or fails gracefully with an assertion error.
- **Actual:** Hard crash of the test worker process.

## Context & Scope
### Regressing Delta
Recent changes in TUI editing workflow or `ConsoleTooling` logic.

### Environmental Triggers
- Windows OS (windows-latest in CI).
- `pytest-xdist` parallel execution.
- TUI Interaction involving external tools (Edit action).

### Ruled Out
- Ubuntu/macOS (both pass).

## Diagnostic Analysis
### Causal Model
1. The test `test_tui_modifying_edit_action_content_succeeds` sets `TEDDY_TEST_MOCK_EDITOR_OUTPUT`.
2. `textual_plan_reviewer_editor.py:launch_editor` detects this environment variable and returns the mock string *immediately*, bypassing `_confirm_and_harvest`.
3. Consequently, NO `ConfirmScreen` (Modal) is ever pushed to the TUI stack.
4. The test pilot, following its script, executes `await pilot.press("y")`.
5. Since there is no modal, the `y` key is unhandled or sent to the `ReviewerApp`, which has no `action_y`.
6. On Windows, this desynchronized input during an async transition can lead to a race condition in the Textual engine or `pytest-xdist` inter-process communication, resulting in a hard worker crash ("node down").

### Discrepancies
- **Crash only on Windows.** (Resolved: Windows terminal/event loop is less resilient to desynchronized input during screen transitions than Unix.)
- **Mock editor skips confirmation.** The mock implementation in `launch_editor` is too "fast", causing the test script to fall out of sync with the UI state.

### Investigation History
1. CI Log Analysis. Identified `test_tui_modifying_edit_action_content_succeeds` as the crash site (worker crash on Windows).
2. Code Audit. Found that `launch_editor` bypassed the confirmation screen when `TEDDY_TEST_MOCK_EDITOR_OUTPUT` was set.
3. Hypothesis. The test pilot was pressing "y" for a confirmation dialog that didn't exist, causing a desynchronization and worker crash on Windows.
4. Repair. Modified `launch_editor` to ensure the mock editor still triggers the confirmation flow.
5. Verification. Remote probe `debug/probe-06` passed on `windows-latest`.

## Solution
### Implemented Fixes
- Modified `src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py` to ensure the `_confirm_and_harvest` logic is executed even when a mock editor is used.

### Prevention
- The existing acceptance test `test_tui_edit_workflow.py` now correctly synchronizes with the UI on all platforms, preventing regression of this terminal handoff logic.
