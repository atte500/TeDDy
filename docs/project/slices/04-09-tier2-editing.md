# Slice: External Editor for Long and Multiline Parameters
- **Status:** In Progress
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
- [x] **Harness** — Expose the launched editor content from the TUI driver so a test can assert what the editor received and feed a replacement value back.
- [x] **Core** — Implement `needs_external_editor` beside `MAX_INLINE_PARAM_LENGTH` with unit tests covering the exact boundary, a multiline value, a joined list, and a scalar.
- [x] **Wiring** — Branch `handle_list_view_selected` on the predicate, route the editor result through `_apply_param_edit`, strip a single editor-appended trailing newline, and prove both branches end to end through the driver.
- [x] **Cleanup** — Update the reviewer component page with the threshold and the branch table.

## Implementation Notes

### Harness — editor handover observability
`TuiDriver` gained a keyword-only `mock_editor_output`. When it is set, the driver exports `TEDDY_TEST_MOCK_EDITOR_OUTPUT`, answers the harness `ISystemEnvironment.create_temp_file` double with a real file under a `tempfile.mkdtemp()` directory, and appends the requested suffix to `editor_launch_suffixes`. A real path matters: the READ/harvest helpers probe the returned path with `os.path.exists` outside their own try block, so a bare mock path would raise instead of returning.

`TuiDriver.get_param_value(pilot, key)` reads the `ParameterDetail` pane's `DetailItem.data`, which is the value the parameter branch would hand to the editor and the value it writes back through `_apply_param_edit`.

**Recorded deviation:** `launch_editor`'s mock branch returns before its own `try/finally`, so it never writes `initial_content` into the temp file and never deletes that file. The handover is therefore proven in three parts rather than by reading the temp file back: the recorded suffix shows the editor path ran instead of the inline modal, `get_param_value` pins the string the branch carries, and the injected replacement landing in `plan.metadata["user_request"]` shows the caller harvested what the hook wrote.

Covered by `tests/suites/unit/test_tui_driver_editor_handover.py`: one `m`-then-`s` journey recording exactly one `.md` handover and harvesting the replacement, one parameter-pane read recording zero handovers.

### Refactor — spec-bound driver defaults
The two bare `MagicMock()` defaults the driver passed as `console_tooling` and `action_dispatcher` were replaced with `Mock(spec=ConsoleToolingHelper)` and `Mock(spec=ActionDispatcher)`. Bare `MagicMock` is banned by TID251 and, worse, answers any attribute, so a drift between the reviewer and those collaborators stayed invisible; the spec-bound doubles fail loudly on an undeclared attribute. Behavior-neutral: the reviewer reaches only `find_editor` and `get_diff_viewer_command`, both declared on `ConsoleToolingHelper`.

### Core — inline budget and trigger predicate
`MAX_INLINE_PARAM_LENGTH = 100` sits beside `MAX_LABEL_LENGTH = 60`, because both are reviewer display budgets rather than user configuration: the milestone fixes the number, so it is a module constant like its neighbour. `needs_external_editor(value)` is the entire trigger, `"\n" in value or len(value) > MAX_INLINE_PARAM_LENGTH`, and three of the slice's edge cases follow directly from its shape. The comparison is strictly greater, so a value at exactly 100 characters keeps the inline modal. Any `\n` triggers, which catches CRLF bodies through their `\n` half while the returned text is stored untouched, so the editor's line endings survive verbatim. And the check runs on the rendered string, so a list is judged after `", ".join` — the same separator `_apply_param_edit` re-splits on — while an integer, float, or boolean arrives already stringified and needs no type branch.

Covered by `tests/suites/unit/adapters/inbound/test_textual_plan_reviewer_helpers.py`: eight parametrized cases (short single line, exactly at budget, one character over, LF multiline, CRLF multiline, joined list within budget, joined list over budget, rendered scalar) plus one test pinning the budget at 100. The pin exists because a boundary case parametrized on the constant alone would silently follow a future change to it and stop proving the milestone's number. Red was `ImportError: cannot import name 'MAX_INLINE_PARAM_LENGTH'`, so the failing gate was the absent capability rather than a broken fixture.

### Wiring — parameter branch and editor handover
`handle_list_view_selected` forks after rendering: a value `needs_external_editor` accepts goes to `launch_editor`, everything else keeps `ParameterEditModal`, and both arms converge on the same `new_val is not None and str(new_val) != str(val)` write-back through `_apply_param_edit`. The `path` guard stays first, so a path is still one token edited through `PathInputScreen`, and the unrenderable-type guard is untouched.

Two orientation findings shaped the branch. First, the pane's value is always a string for action parameters: `resolve_action_parameters` joins a list with the same `", "` separator `_apply_param_edit` re-splits on, and `_render_action_data_detail` stringifies whatever remains. The "non-string scalar" edge case therefore holds structurally — an integer, float, or boolean arrives as `"60.0"` or `"False"`, below the budget and without a newline — so a wiring-level type gate would be an unreachable branch and was not added. Second, `launch_editor` returns `None` for a dismissed edit but an empty string for an emptied buffer, so the arm tests for `None` rather than truthiness; a truthiness test would silently swallow the clear case and leave the old value in place.

`_strip_appended_newline` conditions the trim on the original value: a value that already ended with a newline keeps the edited text untouched, and one that did not loses a single appended break, removed as a pair when the editor wrote Windows line endings. An unconditional strip would rewrite an already terminated command and mark the action modified on a round trip the user never changed.

Covered by `tests/suites/unit/adapters/inbound/test_reviewer_parameter_editor_routing.py`, driven through the real key path — tree focus, three moves onto the action, `tab` into the pane, `enter` on the first row: a multiline RESEARCH query reaching the editor and re-splitting into the list, four EXECUTE permutations (one appended newline stripped, an intentional one preserved, a CRLF pair stripped, an empty result clearing the value), and a short command keeping the inline modal with no handover recorded. Red was `assert [] == ['.txt']` on the editor cases while the inline case passed, which proved the pane journey and isolated the gap to the branch itself.

The emptied-buffer case also exposed a harness fidelity gap the branch could not fix: `launch_editor` gated its mock hook on the variable's truthiness, so an empty replacement behaved exactly like no mock and fell through to the real editor path, returning the unchanged buffer. Gating on the variable's presence makes "the editor returned nothing" representable, which is what the clear case requires.

### Cleanup — single-sourced hook ownership and the component page
The Harness deliverable left the routing module with its own autouse fixture clearing `TEDDY_TEST_MOCK_EDITOR_OUTPUT` after each test, because `TuiDriver` installs that hook process-wide. That guard turned out to be duplicate ownership: `tests/conftest.py` already runs an autouse `clean_test_env` fixture that deletes the variable both before and after every test, so the hook cannot outlive a test in the first place. The honest cleanup was therefore deletion — the fixture and its now-unused `os` import — rather than a second guard, and the 21 cases across the routing, driver-handover, and helpers modules stayed green without it. Because the composition root owns the hook, no entry is needed in [Milestone 6](/docs/project/milestones/06-cross-cutting-consolidation.md), whose consolidated-doubles slice has nothing to absorb here.

The reviewer component page gained a `### Parameter editing` subsection under `## Operations`, as a peer of `### Keyboard bindings` and `### Action log format` — the page's existing precedent for a topic that is neither a method nor a class invariant. It carries the three-arm table (`PathInputScreen` for the `path` key, `launch_editor` for a value `needs_external_editor` accepts, `ParameterEditModal` otherwise) plus the contract notes a reader would otherwise have to infer from the code: the threshold is judged on the rendered string after the `", "` join, exactly 100 characters stays inline, `None` and `""` mean dismissal and clearing respectively, and the single appended newline is trimmed only when the original value did not already end with one. `e` on an action node keeps its own split, so the page states why the two paths differ instead of implying they are one. The page keeps `Status: Refactoring` because milestone 4 still has pending slices editing the same reviewer modules.

The stale-reference sweep came back clean: every hit names a live symbol (`needs_external_editor`, `MAX_INLINE_PARAM_LENGTH`, `_strip_appended_newline`, `ParameterEditModal`) or is this slice's own pre-branch Context narrative, so no renamed or removed component leaves a dangling reference.

## Verification
1. **Multiline value:**
   Build a plan with a RESEARCH action whose query spans three lines, start a session, and press `e` then Tab to that query.
   Verify your editor opens with all three lines and the edited value persists in the parameter list.
2. **Long value:**
   Build a plan with a 240-character EXECUTE command and select it in the parameter list.
   Verify the editor opens instead of the inline modal.
3. **Short value:**
   Select a short parameter and verify the inline modal appears with no editor launch.
