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

Four source files and corresponding test files need to be modified:

1. **`textual_plan_reviewer_previews.py`**: `add_message_handler` — pass `skip_confirm=True`, remove post-editor ConfirmScreen block.
2. **`textual_plan_reviewer_editor.py`**: `launch_editor` — add notification when `find_editor()` returns `None`. `preview_edit_diff_viewer` — add CLI editor suspend/harvest path.
3. **`console_tooling.py`**: `ConsoleToolingHelper` — add `_DIFF_FLAGS` translation table, update `get_diff_viewer_command()`, remove fallback chain from `find_editor()`, remove VS Code special-casing from `_resolve_editor_cmd()`.
4. **`console_interactor_ask_loop.py`**: `_launch_editor_background` — replace silent fallback `or ["vim"]` with notification when no editor is configured.

### Test Harness Strategy

- Use existing `POSIXPathMock` and `MagicMock` fixtures for unit tests.
- TUI tests use `app.run_test()` context manager with `ReviewerApp`.
- Console ask_loop tests use `ConsoleAskLoop` with mocked subprocess/prompt_toolkit.
- New tests for `preview_edit_diff_viewer` CLI editor suspend path in `test_tui_editor_suspend_resume.py`.
- New tests for `get_diff_viewer_command` translation table in `test_console_tooling_editor.py`.
- New tests for no-editor notification in `test_console_ask_loop_editor_background.py` and `test_reviewer_app_core.py`.

## Deliverables

- [ ] **Contract** - Update `ConsoleToolingHelper` public interface: `_DIFF_FLAGS`, `get_diff_viewer_command()` signature change, `find_editor()` behavior change (no fallback).
- [ ] **Harness** - Add test fixtures/mocks for no-editor state, CLI editor classification, diff flag verification.
- [ ] **Seam** - Add `_is_cli_editor()` helper to `textual_plan_reviewer_editor.py` (already exists).
- [ ] **Wiring** - `preview_edit_diff_viewer` CLI editor suspend/harvest path, `add_message_handler` skip_confirm, `launch_editor` no-editor notification, `_launch_editor_background` no-editor notification.
- [ ] **Logic** - `ConsoleToolingHelper._DIFF_FLAGS` translation table, `get_diff_viewer_command()` refactor, `find_editor()` refactor, `_resolve_editor_cmd()` refactor.
- [ ] **Cleanup** - Remove VS Code special-casing from `_resolve_editor_cmd()`, remove fallback chain from `find_editor()`.

## Implementation Notes

(TBD during implementation)

## Verification

1. Run full test suite: `uv run pytest` — all existing tests must pass.
2. Run unit tests for affected modules.
3. Manually verify in TUI: add_message no confirm, diff viewer with vim/nvim, no-editor notification.
4. Verify `get_diff_viewer_command` returns correct commands for known editors.
5. Verify `TEDDY_DIFF_TOOL` env var still overrides the translation table.
6. Verify no editor fallback in console ask loop.
