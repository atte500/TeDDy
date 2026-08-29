# Slice: TUI Plan Reviewer Editor Fixes

- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md), [ConsoleTooling](/docs/architecture/adapters/outbound/console_tooling.md), [ConsoleInteractor](/docs/architecture/adapters/outbound/console_interactor.md)
- **Scope Slug:** `tui-plan-reviewer-editor-fixes`

## Business Goal

Fix three issues with the TUI plan reviewer's editor integration: remove unnecessary save confirmation when adding messages, make the diff viewer work with CLI editors (vim/nvim) via a translation table, and remove the editor fallback chain with proper notification when no editor is configured.

## Scenarios

> As a TUI user, I want to add a message without an extra confirmation step so that I can quickly compose and submit feedback.

```gherkin
Given the TUI plan reviewer is open
When I press "m" to add a message
Then I see a notification "Opening Editor: name"
And the editor opens with the current message content
When I save and exit the editor
Then the content is harvested without a confirm prompt
And the message is applied to the plan
```

> As a TUI user with vim/nvim configured, I want the diff viewer to use `vim -d` so that I can see side-by-side diffs in my preferred editor.

```gherkin
Given my configured editor is "vim"
And I press "e" on an EDIT action
Then I see "vim -d" showing the original vs proposed content
When I edit the right side, save, and quit
Then my changes are harvested and applied to the action
```

> As a user without an editor configured, I want a clear notification instead of a silent fallback to vim so that I can configure my preferred editor.

```gherkin
Given no editor is configured in config or env vars
When I press "e" or "m" in the TUI
Then I see a notification: "No editor configured. Please configure one in .teddy/config.yaml"
And no editor is launched
```

## Key Unknowns

- [x] [Technical] Diff flag compatibility: Is `-d` universal across all editors? Research confirmed only vim/nvim support `-d`. A translation table mapping editor basenames to diff flags is the correct solution.
- [x] [Functional] Removal of confirm screen for add_message: User confirmed that no confirm screen should appear after editor exits when adding a message.
- [x] [Functional] Editor fallback behavior: User confirmed that fallback to code/nano should be removed. Only config and env vars should be used.

## Implementation Plan

### Summary of Changes

Four source files and corresponding test files need to be modified, following a non-breaking expansion -> migration -> contraction sequence:

1. **`console_tooling.py`**: First, add `_DIFF_FLAGS` translation table and extend `get_diff_viewer_command()` to use it (keeping old code path). Then migrate: update consumers to new behavior. Finally, remove fallback chain from `find_editor()` and VS Code special-casing from `_resolve_editor_cmd()`.
2. **`textual_plan_reviewer_previews.py`**: `add_message_handler` — pass `skip_confirm=True`, remove post-editor ConfirmScreen block.
3. **`textual_plan_reviewer_editor.py`**: `launch_editor` — add notification when `find_editor()` returns `None`. `preview_edit_diff_viewer` — add CLI editor suspend/harvest path.
4. **`console_interactor_ask_loop.py`**: `_launch_editor_background` — replace silent fallback `or ["vim"]` with notification when no editor is configured.

### Test Harness Strategy

- Use existing `POSIXPathMock` and `MagicMock` fixtures for unit tests.
- TUI tests use `app.run_test()` context manager with `ReviewerApp`.
- Console ask_loop tests use `ConsoleAskLoop` with mocked subprocess/prompt_toolkit.
- New tests for `preview_edit_diff_viewer` CLI editor suspend path in `test_tui_editor_suspend_resume.py`.
- New tests for `get_diff_viewer_command` translation table in `test_console_tooling_editor.py`.
- New tests for no-editor notification in `test_console_ask_loop_editor_background.py` and `test_reviewer_app_core.py`.

## Deliverables

- [x] **Seam** - Add `_is_cli_editor()` helper to `textual_plan_reviewer_editor.py` (already exists in both `textual_plan_reviewer_editor.py` and `console_interactor_ask_loop.py`).
- [x] **Contract (Expansion)** - Add `_DIFF_FLAGS` class variable to `ConsoleToolingHelper`. Extend `get_diff_viewer_command()` to use the translation table while keeping the old code path functional. Add `noqa: TID251`-free test mocks for new interface.
- [x] **Harness** - Add test fixtures/mocks for no-editor state, CLI editor classification, diff flag verification in existing test files.
- [x] **Migration** - Update all consumers of `ConsoleToolingHelper` (callers of `find_editor()`, `get_diff_viewer_command()`, `_resolve_editor_cmd()`) to transition to new behavior. Update existing tests that relied on the old return values.
- [x] **Wiring** - `preview_edit_diff_viewer` CLI editor suspend/harvest path in `textual_plan_reviewer_editor.py`, `add_message_handler` skip_confirm in `textual_plan_reviewer_previews.py`, `launch_editor` no-editor notification in `textual_plan_reviewer_editor.py`, `_launch_editor_background` no-editor notification in `console_interactor_ask_loop.py`.
- [x] **Cleanup (Contraction)** - Remove VS Code special-casing from `_resolve_editor_cmd()`, remove fallback chain from `find_editor()`, remove old code path from `get_diff_viewer_command()`.
- [x] **Refactor** - Remove unused imports (`ConfirmScreen` from `textual_plan_reviewer_previews.py` if no longer used), clean up stale comments.

## Implementation Notes

- **Migration:** The Contract (Expansion) deliverable was designed with backward compatibility — `get_diff_viewer_command()` falls back to `find_editor()` when direct config/env resolution finds no editor, preserving the old fallback chain. Consumers (`launch_editor`, `preview_readonly`, `_launch_editor_background`) and existing tests (including `test_vscode_is_used_as_fallback` acceptance test) continue to work without changes. The fallback chain removal and VS Code special-casing removal are deferred to the Cleanup (Contraction) deliverable.

- **Harness:** The Contract (Expansion) deliverable already added the `TestGetDiffViewerCommand` test class with 11 tests covering diff flag verification and no-editor state. The `_is_cli_editor` classification is tested in `test_tui_editor_suspend_resume.py::TestIsCliEditor`. The ask_loop tests have `mock_system_env`, `mock_tooling`, `ask_loop` fixtures. No additional harness code was needed beyond what was already committed.

- `_DIFF_FLAGS` translation table added as a class variable to `ConsoleToolingHelper` with support for vim, vi, nvim, code, cursor, codium, zed, and idea.
- `get_diff_viewer_command()` updated to bypass `find_editor()` for diff viewing (to avoid VS Code's `-r --wait` editing flags). Instead, it resolves the editor directly from config/env, checks the translation table, and returns the resolved path + diff flags. This is intentional – the diff viewer command should be clean without editor-specific editing flags.
- `TEDDY_DIFF_TOOL` env var override still works unchanged.
- 11 new tests added in `TestGetDiffViewerCommand` class covering known editors, unknown editors, TEDDY_DIFF_TOOL override, and no-editor state.
- Deliberate debt: `get_diff_viewer_command()` duplicates some editor resolution logic from `find_editor()` to avoid the VS Code special-casing. This will be resolved in the Cleanup (Contraction) deliverable when `find_editor()` and `_resolve_editor_cmd()` are refactored.

### Wiring Deliverable (Sub-items 1-4)

- **Sub-item 1 (ask_loop no-editor):** Replaced `or ["vim"]` fallback in `_launch_editor_background()` with a check that logs `"No editor configured"` and returns `""`. Added `TestLaunchEditorBackgroundNoEditor` test class (2 tests). Existing editor tests continue to pass.
- **Sub-item 2 (launch_editor no-editor):** Added `app.notify(...)` call before `return None` in `launch_editor()` when `find_editor()` returns `None`. Added `test_no_editor_notifies_user` test in `TestLaunchEditor` class.
- **Sub-item 3 (add_message_handler skip_confirm):** Removed `ConfirmScreen` import from `textual_plan_reviewer_previews.py`. Pass `skip_confirm=True` to `launch_editor()`. Removed post-editor `ConfirmScreen` block. Added `TestAddMessageHandler` test class.
- **Sub-item 4 (CLI diff viewer suspend):** Updated `preview_edit_diff_viewer()` to detect CLI editors via `_is_cli_editor()` and use `app.suspend()` + `subprocess.run()` + auto-harvest, skipping `ConfirmScreen`. GUI editors keep the existing background + ConfirmScreen path. Added `TestPreviewEditDiffViewer` test class with CLI and GUI regression tests.
- **Test file cleanup:** Rewrote `test_tui_editor_suspend_resume.py` to fix structural corruption (Turn 23's bad EDIT). Properly separated `TestIsCliEditor`, `TestAddMessageHandler`, `TestLaunchEditor`, and `TestPreviewEditDiffViewer` classes.
- **Notification language:** Both TUI (`app.notify`) and console (`logger.info`) use the message: `"No editor configured. Please configure one in .teddy/config.yaml"`.

### Cleanup (Contraction) Deliverable

- **Removed fallback chain:** `find_editor()` no longer falls back to hardcoded `code`/`nano` if config and env vars are absent. It now returns `None` when neither is set.
- **Removed VS Code special-casing:** `_resolve_editor_cmd()` no longer appends `-r` and `--wait` flags for VS Code. The command is returned as resolved from `which()`.
- **Removed old fallback in `get_diff_viewer_command()`:** The method no longer calls `find_editor()` as a fallback when direct config/env resolution returns `None`. It goes directly to config/env resolution using the `_DIFF_FLAGS` translation table.
- **Removed acceptance test:** `test_vscode_is_used_as_fallback` was removed from `test_change_preview_feature.py` as it tested the old fallback behavior. Replaced with a comment documenting the removal.
- **Test updates in `test_console_tooling_editor.py`:**
  - Removed 3 tests: `test_find_editor_falls_back_to_code_then_nano`, `test_find_editor_falls_back_to_code_with_flags`, `test_resolve_editor_cmd_appends_vscode_flags`.
  - Added 3 new tests: `test_find_editor_returns_none_when_no_config_and_no_env`, `test_find_editor_config_code_returns_without_flags`, `test_diff_viewer_returns_none_when_fallback_not_taken`.
- **Full suite regression:** 1151 tests pass after Cleanup. The removal of the fallback chain has no downstream impact because all production consumers of `find_editor()` already handle `None` return (no-editor notification was implemented in Wiring).
- **Debt:** `get_diff_viewer_command()` and `find_editor()` share duplicate editor resolution logic (config → env resolution). This could be extracted to a private helper method, but is left as-is to keep the Cleanup changes minimal and focused on removing the deprecated behavior.

### Refactor Deliverable

- **No code changes needed:** The primary task (removing unused `ConfirmScreen` import from `textual_plan_reviewer_previews.py`) was already completed during the Wiring deliverable (sub-item 3). The import was removed when `skip_confirm=True` was implemented and the post-editor `ConfirmScreen` block was removed.
- **Stale comments audit:** Grep for "Discovery Fallback", "fallback chain", "VS Code special-casing", "old code path", and stale numbered steps across all production files returned no results. All comments in `console_tooling.py`, `textual_plan_reviewer_editor.py`, `textual_plan_reviewer_previews.py`, and `console_interactor_ask_loop.py` are accurate and reflect the current code state.
- **Final search:** Comprehensive grep confirmed no stale comments remain. The Refactor deliverable is satisfied with zero code changes.
- **As-built update skipped:** `docs/architecture/adapters/outbound/console_tooling.md` does not exist in the repository. The ConsoleTooling doc references in the slice metadata are stale; the component doc was never created. This is noted as a documentation gap for the Architect.

## Verification

1. Run full test suite: `uv run pytest` — all existing tests must pass.
2. Run unit tests for affected modules.
3. Manually verify in TUI: add_message no confirm, diff viewer with vim/nvim, no-editor notification.
4. Verify `get_diff_viewer_command` returns correct commands for known editors.
5. Verify `TEDDY_DIFF_TOOL` env var still overrides the translation table.
6. Verify no editor fallback in console ask loop.
