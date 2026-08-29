# Slice: TUI Annotated Edit Diff
- **Status:** In Progress
- **Milestone:** Milestone 4: TUI & UX Enhancements
- **Specs:** [TUI Plan Reviewer Editor Fixes](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Prototype:** [spikes/single_file_diff_spike.py]
- **Component Docs:** [TextualPlanReviewer Editor](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `tui-annotated-edit-diff`

## Business Goal

Replace the vimdiff two-file flow (`nvim -d before after`) with a single `.diff` file containing annotated unified diff markers, providing a clean single-file editing experience with no `:q` window-closing confusion, while preserving the ability to preview and edit proposed changes.

## Scenarios

> As a user of the TUI plan reviewer, I want to press `e` on an EDIT action and have the changes shown as an annotated single-file diff, so that I can review and edit changes without vimdiff's confusing two-window layout.

```gherkin
Given I am in the TUI plan reviewer with an EDIT action selected
When I press `e` on the unfocused preview pane
Then a single `.diff` file opens in my terminal editor
And the file contains annotated unified diff markers showing the original vs proposed changes
And I can edit `+` lines to modify the proposed content
And when I save and exit with `:q`, the proposed content is updated with my changes
```

## Edge Cases

- **Empty diff (original == proposed):** `reconstruct_from_diff` should return the original content unchanged, as there are no `+` or `-` lines in the diff.
- **Only additions (no deletions):** All `+` lines should be kept with prefix stripped, no `-` lines to discard.
- **Only deletions (no additions):** `-` lines should be discarded entirely, context lines kept, no `+` lines in output.
- **Mixed modifications:** Both additions and deletions should be handled correctly — `-` lines removed, `+` lines kept with prefix stripped.
- **No file changes (user exits without editing):** If the user reads the diff and exits without modifying, the proposed content remains unchanged (no new edits harvested).
- **User modifies `-` lines:** Modified `-` lines should be discarded during reconstruction — user edits to removed lines are harmless and ignored.
- **User modifies `+` lines:** Modified `+` lines should be kept with the `+` prefix stripped — this is the primary editing mechanism.
- **User adds new lines without prefix:** Lines without `-` or `+` prefix are context lines and should be kept as-is.
- **GUI editor path unchanged:** Pressing `e` with code/cursor should continue to use the existing `code --diff` two-file flow.

## Key Unknowns

No key unknowns identified for this feature. The annotated diff approach was validated via spike (`spikes/single_file_diff_spike.py`).

## Implementation Plan

The implementation follows the Tracer Bullet Dependency Sequence:
1. **Logic**: Pure functions for diff reconstruction and annotated diff generation
2. **Wiring**: Update `preview_edit_diff_viewer()` CLI branch to use annotated diff
3. **Migration**: Move `_setup_before_file()` inside GUI branch
4. **Cleanup**: Remove unnecessary parameters and old functions

### Key Design Decisions

- `reconstruct_from_diff()` and `_generate_annotated_diff_content()` are pure functions placed in `textual_plan_reviewer_editor.py` (the editor module) since that's where the diff viewer lives.
- `_generate_annotated_diff_content()` uses `difflib.unified_diff()` directly rather than the existing `generate_unified_diff()` in `diff.py`, to keep the annotated content generation colocated with the editor logic.
- The annotated diff file uses `.diff` extension for automatic vim syntax highlighting.
- `handle_mock_diff()` currently takes `before` parameter — this will be refactored in the Migration phase to separate cleanup from the mock diff writing logic.

## Deliverables

- [▶] **Logic** — Implement `reconstruct_from_diff()` with unit tests
- [ ] **Logic** — Implement `_generate_annotated_diff_content()` with unit tests
- [ ] **Wiring** — Update `preview_edit_diff_viewer()` CLI branch to use annotated diff, add integration test for end-to-end flow
- [ ] **Migration** — Move `_setup_before_file()` inside GUI branch, update `handle_mock_diff()` to not require `before` parameter
- [ ] **Cleanup** — Remove `_setup_before_file()` and `harvest_edit_diff()` if no longer needed, remove `before` parameter from `handle_mock_diff()`

## Verification

1. Run unit tests for `reconstruct_from_diff()` — verify all edge cases (empty diff, additions only, deletions only, mixed, modified `-` lines, modified `+` lines)
2. Run unit tests for `_generate_annotated_diff_content()` — verify header format, unified diff format, edge cases
3. Run full test suite — all tests must pass
4. Manually verify in TUI:
   - Press `e` on an EDIT action with vim/nvim — single `.diff` file opens, `:q` exits cleanly
   - Edit a `+` line — edit appears in reconstructed content
   - Edit a `-` line — edit is discarded
   - GUI editor (code/cursor) — existing `code --diff` flow works unchanged
