# Bug: Session View Plan Path

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../project/milestones/10-interactive-session-and-config.md)

## Symptoms
When using the `view plan` feature in session mode:
1. It opens a temporary version of the plan instead of the actual `plan.md` in the session directory.
2. It does not open in read-only mode (it might be checking for changes unnecessarily).

## Context & Scope
### Regressing Delta
TBD - Likely introduced during the TUI Instruction Bridge or Session implementation.

### Environmental Triggers
- Session mode active.
- TUI plan reviewer active.

### Ruled Out
TBD

## Diagnostic Analysis
### Causal Model
When the "View Plan" action is triggered in the TUI:
1. `view_plan_handler` is invoked.
2. It correctly identifies `app.plan.plan_path`.
3. It reads the content of the file.
4. It calls `launch_editor(app, content, suffix=".md")`.
5. `launch_editor` receives the content but no `persistent_path`, causing it to generate a new temporary file for the editor session.

### Discrepancies
- Handler knows the real path but doesn't pass it to the editor driver. (Confirmed via MRE)
- Handler provides content to `launch_editor` which usually implies an editable buffer, whereas this view should be read-only.

### Investigation History
1. Search for "view plan" in TUI adapters. Found binding in `textual_plan_reviewer_app.py`.
2. Traced call to `view_plan_handler` in `textual_plan_reviewer_previews.py`.
3. Verified via MRE that `launch_editor` is called without `persistent_path`.
4. Applied fix to pass `persistent_path` and `skip_confirm=True` to `launch_editor`.
5. Verified "Test the Test": New regression test passes with fix and fails without it.

## Solution
### Implemented Fixes
- Modified `view_plan_handler` in `textual_plan_reviewer_previews.py` to pass `app.plan.plan_path` as the `persistent_path` to `launch_editor`.
- Set `skip_confirm=True` in the `launch_editor` call to ensure the "View Plan" action remains informational and doesn't prompt for buffer-to-plan harvesting.

### Prevention
- Added a formal unit test `tests/suites/unit/adapters/inbound/test_view_plan_regression.py` that mocks `launch_editor` and asserts that the `persistent_path` and `skip_confirm` arguments are correctly passed.
