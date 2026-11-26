# Slice: External Editor for Long and Multiline Parameters
- **Status:** Planned
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `tier2-editing`

## Goal
Open a parameter in the user's editor when its value is multiline or too long for one line, so fixing a long command or a file body stops degrading into horizontal scrolling inside a single-line input.

## Context
- `handle_list_view_selected` (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py`): For a non-path key it renders the value — a list joined with `", "`, otherwise `str(val)` — and always pushes `ParameterEditModal(f"{key}:", v_str)`. There is no length or multiline branch.
- `ParameterEditModal` (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py`): Composes one `Input`, dismisses on submit, and cancels on `escape`. An `Input` is single-line by construction, so a pasted body loses its line breaks and a long value scrolls horizontally.
- `launch_editor(app, content, suffix=..., persistent_path=..., skip_confirm=...)` (`textual_plan_reviewer_editor.py`): The seam every other reviewer edit already uses — `preview_create`, `preview_text_action`, and `add_message_handler` all call it and harvest the returned string.
- `_apply_param_edit(action, key, new_val)` (`textual_plan_reviewer_helpers.py`): Splits `queries` and `reference_files` on commas and stores every other key verbatim as a string, so a multiline body round-trips intact through the same write path the modal uses.
- `handle_edit_action`: The `e` path already delegates CREATE and EDIT bodies to the editor, so the length rule only concerns the parameter list in the right pane.
- `MAX_LABEL_LENGTH = 60` (`textual_plan_reviewer_helpers.py`): Precedent that a reviewer-side display budget lives as a module constant rather than a config key.
- `DetailItem.MAX_PREVIEW_LENGTH = 20000` and `TRUNCATE_HALFWAY`: Only the pane preview truncates; the underlying parameter value stays intact.
- Milestone 4, Requirement "Tier 2 Editing": Fixes the trigger — a parameter that is multiline or longer than 100 characters opens in the external editor.

## Scenarios

> As a reviewer, I want to fix a multi-line command without losing its newlines.

```gherkin
Given a RESEARCH action with a query carrying several newline-separated lines
When I select that query in the parameter list
Then my editor opens with the value
And submitting it writes the edited text back, newlines included
```

> As a reviewer, I want a very long single-line value to open in my editor.

```gherkin
Given an EXECUTE action whose command is 240 characters long
When I select the command in the parameter list
Then my editor opens with the command
```

> As a reviewer, I want short values to stay inline so editing stays fast.

```gherkin
Given a parameter whose value is a single 20-character line
When I select it in the parameter list
Then the inline modal opens and no editor is launched
```

## Edge Cases
- **Threshold boundary**: If a value is exactly 100 characters, then the inline modal opens, because the rule triggers only above the budget.
- **Joined list value**: If a list value exceeds the budget only after joining with `", "`, then the editor opens and the returned text is re-split on commas, because the separator is the list contract.
- **Cancelled edit**: If the editor exits without a change or is dismissed, then the parameter is untouched, because an abandoned edit must be inert.
- **Empty result**: If the editor returns an empty string, then the parameter is cleared, because the modal already permits clearing and the two paths must agree.
- **Trailing newline**: If the editor appends one newline to a value that had none, then exactly one trailing newline is stripped, because many editors add it and a command must not gain a stray line break.
- **Path key**: If the selected key is `path`, then `PathInputScreen` still handles it, because a path is a single token and the file picker semantics stay unchanged.
- **CRLF**: If the editor returns Windows line endings, then the value is stored verbatim, because rewriting line endings would silently mutate file bodies the user did not touch.
- **Non-string scalar**: If the value is an integer, float, or boolean, then the inline modal opens regardless of length, because a scalar has no multiline representation.
- **Unrendered value**: If the value is a type the reviewer cannot edit, then nothing opens, because the existing guard must keep rejecting it.

## Key Unknowns
- None. The trigger is a pure function of the value, and the editor seam already exists and is already used by three sibling paths, so no prototype is needed.

## Impact
1. `[NEW]` `needs_external_editor(value: str) -> bool` and `MAX_INLINE_PARAM_LENGTH = 100` in `textual_plan_reviewer_helpers.py` — the single trigger predicate beside the existing label budget.
2. `[MIGRATE]` `handle_list_view_selected` — branch on the predicate, routing long or multiline values through `launch_editor` and everything else through `ParameterEditModal`, then applying the result through the existing `_apply_param_edit`.
3. `[NEW]` Unit coverage over the predicate and the branch, driven through the existing TUI driver so the editor call is observable without a real editor.
4. `[MIGRATE]` The reviewer component page — record the trigger threshold and the three-way branch for `e` and for parameter selection.

## Deliverables
- [ ] **Harness** — Expose the launched editor content from the TUI driver so a test can assert what the editor received and feed a replacement value back.
- [ ] **Core** — Implement `needs_external_editor` beside `MAX_INLINE_PARAM_LENGTH` with unit tests covering the exact boundary, a multiline value, a joined list, and a scalar.
- [ ] **Wiring** — Branch `handle_list_view_selected` on the predicate, route the editor result through `_apply_param_edit`, strip a single editor-appended trailing newline, and prove both branches end to end through the driver.
- [ ] **Cleanup** — Update the reviewer component page with the threshold and the branch table.

## Implementation Notes

## Verification
1. **Multiline value:**
   Build a plan with a RESEARCH action whose query spans three lines, start a session, and press `e` then Tab to that query.
   Verify your editor opens with all three lines and the edited value persists in the parameter list.
2. **Long value:**
   Build a plan with a 240-character EXECUTE command and select it in the parameter list.
   Verify the editor opens instead of the inline modal.
3. **Short value:**
   Select a short parameter and verify the inline modal appears with no editor launch.
