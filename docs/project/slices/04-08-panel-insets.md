# Slice: Uniform Panel Insets Across the Reviewer
- **Status:** Completed
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `panel-insets`

## Goal
Give the reviewer one inset for both panes and every row, so rationale text, context rows, parameter rows, and the action tree all start at the same gutter instead of three different ones.

## Context
- `TUI_CSS` (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py`): Declares `#left-pane` at `width: 65%` with no inset, `#right-pane` at `padding: 0` plus `border-left: vkey $foreground 15%`, `#rationale-content` at `padding: 1 2`, and `ListItem` at `padding: 0 1`. `Tree` declares no inset at all, so four selectors carry three different gutters.
- Visible consequence: rationale prose starts two columns in, a parameter row starts one column in, a context row starts flush against the pane edge, and the action tree sits flush against the terminal edge.
- `#right-pane` is a container that swaps `RationaleDetail` (`VerticalScroll` hosting `#rationale-content`) for `ParameterDetail` (`ListView` of `ListItem`), so a container-level inset applies to both variants at once while a per-widget inset must be repeated in every branch.
- `ListItem.--highlight` paints the row background, so the highlight band width is a visible consequence of where the inset lives.
- `DetailItem` wraps its value in `Static(expand=True)` and relies on the list item for its gutter, so removing the item inset without adding a container inset would leave parameters flush.
- No test pins any of these values today, so the numbers can drift silently; a stylesheet-wide assertion is the only deterministic guard available, because Textual layout is not observable from the harness without a screenshot.
- Milestone 4, Requirement "Layout Padding Consistency": Fixes the target — one consistent padding across the left panel and every right-panel case.

## Scenarios

> As a reviewer, I want every panel to breathe the same amount so the layout reads as one surface.

```gherkin
Given the reviewer is open with a context panel and a plan
When I compare the first character of a rationale line, a parameter row, and a context row
Then all three start at the same column
And the action tree starts at that same column
```

> As a reviewer, I want the highlight band to stay inside the panel rather than touching the border.

```gherkin
Given a parameter list with the cursor on a row
When the row is highlighted
Then the highlight band starts at the panel's gutter and never overlaps the left border
```

## Edge Cases
- **Doubled inset**: If the container and a child both declare an inset, then the panes drift apart again, because CSS padding stacks; only one level may carry the value.
- **Narrow terminal**: If the terminal is narrow enough that the 35% right pane loses most of its width, then the horizontal inset still applies and the content wraps rather than clipping, because the inset must scale with the pane, not with the terminal.
- **Border adjacency**: If `#right-pane` keeps its `border-left`, then the inset sits inside the border, because padding is drawn within the border box.
- **Empty right pane**: If no node is selected and the right pane renders nothing, then the left pane keeps its inset, because the inset is declared per pane rather than inherited from a mounted child.
- **Long unwrapped row**: If a row's text exceeds the pane width, then it wraps inside the inset instead of scrolling under the border, because the inset reduces the available width rather than offsetting the content.
- **Focus change**: If focus moves between panes, then the inset is unchanged, because the inset is not tied to the focus state.

## Key Unknowns
- None. The target is a single value applied at one level, and the stylesheet is a static string, so the outcome is fully determined by the rendered CSS that the harness asserts.

## Impact
1. `[NEW]` `PANEL_INSET` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py` — the vertical and horizontal inset pair, the single source of truth for every panel gutter.
2. `[NEW]` `build_tui_css()` in the same module — renders `TUI_CSS` as a template, substituting the inset so no selector hardcodes it.
3. `[MIGRATE]` `#left-pane` and `#right-pane` — carry the inset; `#rationale-content`, `ListItem`, and `Tree` stop declaring their own.
4. `[NEW]` Harness helper in `tests/harness/` — parses the stylesheet into selector → declarations so a test asserts each pane's padding without matching the whole string.
5. `[MIGRATE]` The reviewer component page — record the single-inset rule beside the layout description.

## Deliverables
- [x] **Harness** — Add a stylesheet parser to the harness that returns `{selector: {property: value}}`, so padding can be asserted per selector and a future duplicate declaration fails with a readable diff.
- [x] **Adapter** — Introduce `PANEL_INSET` with `build_tui_css()`, apply the inset to both pane containers, and remove the per-child inset declarations, proving the substitution with a unit test over the rendered stylesheet.
- [x] **Cleanup** — Record the one-inset rule in the reviewer component page and delete the now-unused precedent of per-widget padding.

## Implementation Notes
- **Parser home:** `parse_stylesheet` lives in `tests/harness/observers/stylesheet_parser.py`, not `tests/harness/setup/`, because it turns a production artifact back into a structure for assertions — the same job `ReportParser` does for report Markdown. Its guard, `tests/suites/unit/test_stylesheet_parser.py`, sits at the unit-suite root beside `test_report_parser.py`, matching the existing observer convention.
- **Parse ordering:** comments are stripped before block matching, so a comment inside a block cannot surface as a bogus declaration, and each comma-expanded selector receives its own declarations dict, so a sibling selector never aliases another's properties. Textual `$variables` and composite values such as `vkey $foreground 15%` are kept verbatim, because the stylesheet is asserted as written rather than resolved.
- **Box-model probe:** a 40-column Textual probe with `width: 50%` plus `padding: 0 1` measured `outer_width 20` for both panes with the second starting at `x 20`, so percentage width is a border-box measure. The inset can therefore be added to `#left-pane` and `#right-pane` without overflowing the 65/35 split, and no `1fr` width migration is needed.
- **Public artifact preserved:** `TUI_CSS = build_tui_css(PANEL_INSET)` stays a module-level string, so `ReviewerApp.CSS = TUI_CSS` keeps binding at import with no app-module change. Five slices edit the reviewer seam, so leaving the app untouched keeps their rebase surface minimal while the builder remains independently testable with arbitrary pairs.
- **Sentinel substitution:** the template carries `__PANEL_INSET__` and `build_tui_css` replaces it, because this stylesheet defeats every standard mechanism — `str.format` and `%` collide with the literal `65%` and the `{}` blocks, and `string.Template` collides with Textual's own `$surface` variables. The inset is a required argument rather than a defaulted constant, so a test proves substitution without patching a module global.
- **Inset value `(1, 2)`:** the pair rationale prose already used (`padding: 1 2`), so the richest right-panel variant does not shrink, while the parameter list trades its `0 1` for the same one-line breathing room. It is declared on the two pane containers only; `#rationale-content` and `ListItem` lost their declarations because CSS padding stacks and a surviving child inset would put that row back on a different gutter.
- **One-level proof:** `tests/suites/unit/adapters/inbound/test_reviewer_stylesheet.py` asserts the shipped `ReviewerApp.CSS` carries the inset on both panes, that none of `#rationale-content`, `ListItem`, or `Tree` re-declares a padding, that `#right-pane` keeps its `border-left`, and that four arbitrary pairs render through `build_tui_css` — so a reintroduced child inset fails with a selector-named diff rather than silently reintroducing the drift.
- **Documentation half of the cleanup:** the per-widget padding precedent was already gone from the code when the Adapter change landed, because CSS padding stacks and a surviving child declaration would have undone the fix. What remained was prose: the reviewer page now states the rule as the `single_panel_inset` invariant beside the dual-pane layout description and its `review` postcondition names the shared gutter, so no page still describes four separate gutters. The parser is documented as As-Built at `docs/architecture/tests/observers/stylesheet_parser.md` and linked from the Component Map's Test Harness table beside `ReportParser`, because both are inverse adapters that turn a production artifact back into a structure for assertions.
- **Verification audit:** the seam has exactly three consumers — the widgets module (constant, sentinel, template, builder, `TUI_CSS = build_tui_css(PANEL_INSET)`), the app's `CSS = TUI_CSS` binding, and the contract test — with no orphaned helper and no literal inset left anywhere under `adapters/inbound/`. The contract test imports `PANEL_INSET` rather than restating `(1, 2)`, so both sides read the single source of truth. The two surviving `padding: 0 1` strings are arbitrary CSS input inside `test_stylesheet_parser.py`, proving declaration parsing and comma expansion, so they carry no coupling to the reviewer's stylesheet and stay put. No lint rule was added: the one-gutter invariant is already enforced per selector against the shipped `ReviewerApp.CSS`, which is stronger than a text match over the module.

## Verification
1. **Gutter alignment:**
   Run `uv run teddy start -m "plan a small refactor"` and move the cursor from a context row to a rationale section to a parameter row.
   Verify all three begin at the same column and the action tree matches them.
2. **Highlight band:**
   Press Tab into the parameter list and step through rows.
   Verify the highlight band starts at the gutter and never touches the left border.
