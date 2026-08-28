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
- [ ] **Migration** - Update all consumers of `ConsoleToolingHelper` (callers of `find_editor()`, `get_diff_viewer_command()`, `_resolve_editor_cmd()`) to transition to new behavior. Update existing tests that relied on the old return values.
- [ ] **Wiring** - `preview_edit_diff_viewer` CLI editor suspend/harvest path in `textual_plan_reviewer_editor.py`, `add_message_handler` skip_confirm in `textual_plan_reviewer_previews.py`, `launch_editor` no-editor notification in `textual_plan_reviewer_editor.py`, `_launch_editor_background` no-editor notification in `console_interactor_ask_loop.py`.
- [ ] **Cleanup (Contraction)** - Remove VS Code special-casing from `_resolve_editor_cmd()`, remove fallback chain from `find_editor()`, remove old code path from `get_diff_viewer_command()`.
- [ ] **Refactor** - Remove unused imports (`ConfirmScreen` from `textual_plan_reviewer_previews.py` if no longer used), clean up stale comments.

## Implementation Notes

- **Harness:** The Contract (Expansion) deliverable already added the `TestGetDiffViewerCommand` test class with 11 tests covering diff flag verification and no-editor state. The `_is_cli_editor` classification is tested in `test_tui_editor_suspend_resume.py::TestIsCliEditor`. The ask_loop tests have `mock_system_env`, `mock_tooling`, `ask_loop` fixtures. No additional harness code was needed beyond what was already committed.

- `_DIFF_FLAGS` translation table added as a class variable to `ConsoleToolingHelper` with support for vim, vi, nvim, code, cursor, codium, zed, and idea.
- `get_diff_viewer_command()` updated to bypass `find_editor()` for diff viewing (to avoid VS Code's `-r --wait` editing flags). Instead, it resolves the editor directly from config/env, checks the translation table, and returns the resolved path + diff flags. This is intentional – the diff viewer command should be clean without editor-specific editing flags.
- `TEDDY_DIFF_TOOL` env var override still works unchanged.
- 11 new tests added in `TestGetDiffViewerCommand` class covering known editors, unknown editors, TEDDY_DIFF_TOOL override, and no-editor state.
- Deliberate debt: `get_diff_viewer_command()` duplicates some editor resolution logic from `find_editor()` to avoid the VS Code special-casing. This will be resolved in the Cleanup (Contraction) deliverable when `find_editor()` and `_resolve_editor_cmd()` are refactored.

## Verification

1. Run full test suite: `uv run pytest` — all existing tests must pass.
2. Run unit tests for affected modules.
3. Manually verify in TUI: add_message no confirm, diff viewer with vim/nvim, no-editor notification.
4. Verify `get_diff_viewer_command` returns correct commands for known editors.
5. Verify `TEDDY_DIFF_TOOL` env var still overrides the translation table.
6. Verify no editor fallback in console ask loop.
