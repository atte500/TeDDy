# Slice: Rationale Sections as Authored
- **Status:** Completed
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** [Plan Format](/docs/project/specs/plan-format.md)
- **Prototype:** None
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `rationale-sections`

## Goal
Render a rationale exactly as its author wrote it — one node per `###` heading — so a plan that renames, adds, or reorders a section is reviewable instead of having that section silently folded into the one before it, and so a header-less rationale is labelled `Untitled` rather than `Raw`.

## Context
- `rationale_entries` (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`, imported by `handle_mount_logic`): Splits the rationale on `\n(?=### )` and keeps a node only when its title is in `ALLOWED_RATIONALE_SECTIONS` (`Summary`, `Expectation`, `Progress`, `Notes`); every other chunk merges into the preceding node, and a rationale with no recognized heading renders as one `RATIONALE_FALLBACK_TITLE` node.
- `recognized_rationale_sections`: The helper behind that filter. Together with `ALLOWED_RATIONALE_SECTIONS` and `rationale_entries` it forms three entry points for one behavior, so the milestone constraint collapses them into a single `rationale_sections`.
- The split is fence-blind: a `### ` line inside a fenced block currently merges into its predecessor, and naively splitting on the marker would tear a code fence in half, producing two nodes whose bodies are invalid Markdown.
- `handle_mount_logic` (`textual_plan_reviewer_helpers.py`): Consumes the entries, styles the fallback title with `[#888888 italic]` so it reads quieter than a protocol section, and adds each node as a `{"type": "RATIONALE_SECTION", "title": ..., "content": ...}` payload.
- `populate_context_detail` and the detail pane read `title` and `content` straight off that payload, so the splitter is free to emit any titles the rationale carries.
- The four canonical sections remain the authored contract in the plan-format spec; only the reviewer's parser restriction is being removed, not the protocol.
- Two tests pin the behavior being removed — `test_tui_only_accepts_markdown_headings` and `test_recognized_rationale_sections_merge_unrecognized_headings` — and must be replaced rather than relaxed.
- The `rationale_heading_only` invariant in the reviewer component page states the restriction and flips in the same commit as the code.
- `RATIONALE_FALLBACK_TITLE` (`textual_plan_reviewer_logic.py:30`) currently reads `Raw`, its two docstrings (`:52`, `:75`) repeat the word, and the reviewer page's invariant names it too. A rationale carrying no heading is not raw text — it is an untitled section — so the label becomes `Untitled` in the same commit as the splitter rewrite, and the page keeps describing `Raw` until that commit lands.

## Scenarios

> As a reviewer, I want a non-protocol section to get its own node.

```gherkin
Given a rationale carrying "### Context" and "### Trade-offs" headings
When the reviewer builds its tree
Then Rationale contains a Context node and a Trade-offs node
```

> As a reviewer, I want a heading inside a fenced example to stay in its section.

```gherkin
Given a rationale whose Notes section embeds a fenced block containing a "### " line
When the reviewer builds its tree
Then the fenced line stays inside the Notes node
And no extra node appears for it
```

> As a reviewer, I want text before the first heading to remain visible.

```gherkin
Given a rationale that opens with a paragraph before its first heading
When the reviewer builds its tree
Then a leading Untitled node holds that paragraph
```

## Edge Cases
- **No heading at all**: If the rationale carries no `### ` line, then one quieter `Untitled` node holds the whole body, because pre-contract plans and archived sessions must stay reviewable and `Raw` mislabels authored prose as machine output.
- **Four hashes**: If a line starts with `#### `, then it does not split, because only a level-three heading is a section boundary.
- **Tilde fence**: If a fenced block uses tildes instead of backticks, then its contents are ignored for splitting, because both fence styles are legal Markdown.
- **Longer fence**: If a fence is opened with four or more backticks, then only a fence of at least that length closes it, because a shorter run is content inside the block.
- **Unclosed fence**: If the rationale ends inside an open fence, then nothing after the opening fence splits, because a torn fence is worse than a merged section.
- **Empty section**: If a heading is immediately followed by another heading, then the first node carries an empty body rather than disappearing, because the author's structure must be preserved.
- **Duplicate titles**: If two sections share a title, then both nodes appear in order, because the tree is a view of the text, not a keyed map.
- **Trailing whitespace**: If a heading line ends with spaces, then the title is stripped, because a trailing space must not leak into the label.
- **Indented heading**: If the heading is indented by spaces, then it does not split, because an indented line is body content.

## Key Unknowns
- None. The split is a pure string transformation with a fully enumerated rule set, and the mount path already consumes a title/content list, so no prototype is needed.

## Impact
1. `[NEW]` `rationale_sections(rationale: str) -> list[tuple[str, str]]` in `textual_plan_reviewer_logic.py` — a fence-aware splitter returning every section in authored order, with a leading `Untitled` entry for preamble text, and `RATIONALE_FALLBACK_TITLE` renamed to `Untitled` as its fallback label.
2. `[PRUNE]` `ALLOWED_RATIONALE_SECTIONS`, `recognized_rationale_sections`, and `rationale_entries` — deleted once the mount path uses the new entry point.
3. `[MIGRATE]` `handle_mount_logic` — consume `rationale_sections` and keep the quieter styling for whichever entry is the fallback.
4. `[MIGRATE]` `test_tui_only_accepts_markdown_headings` and `test_recognized_rationale_sections_merge_unrecognized_headings` — replaced by tests over the fence-aware rules.
5. `[MIGRATE]` The reviewer component page's `rationale_heading_only` invariant — restated as "every level-three heading is a section, fences respected, preamble preserved, and a heading-less rationale renders as `Untitled`".

## Deliverables
- [x] **Harness** — Add a rationale fixture builder emitting preamble, protocol sections, non-protocol sections, and fenced blocks with `### ` content, so every splitter branch is drivable from one helper.
- [x] **Adapter** — Implement `rationale_sections` as a pure fence-aware splitter in `textual_plan_reviewer_logic.py` with unit tests in `tests/suites/unit/adapters/inbound/test_rationale_sections.py` covering the preamble, the four-hash line, tilde and long fences, an unclosed fence, an empty section, duplicates, and an indented heading; rename `RATIONALE_FALLBACK_TITLE` to `Untitled` with its two docstrings and update the `["Raw"]` label assertion in the sectionless acceptance test so the suite stays green.
- [x] **Wiring** — Switch `handle_mount_logic` onto `rationale_sections`, preserving the quieter fallback styling, replace `test_tui_only_accepts_markdown_headings` with an acceptance test proving a non-protocol heading reaches the tree, and keep the sectionless test green against the new splitter.
- [x] **Refactor** — Delete `ALLOWED_RATIONALE_SECTIONS`, `recognized_rationale_sections`, and `rationale_entries`, move `_rationale_content`'s surviving coverage into `test_rationale_sections.py`, and delete `test_section_filtering.py`, keeping the suite green throughout.
- [x] **Cleanup** — Restate the `rationale_heading_only` invariant in the reviewer component page as the new fence-aware rule, with `Untitled` as the fallback label, note that the quieter styling keys on the title string, and restate `_rationale_content`'s stale "whole-block fallback" docstring in the same commit.
- [x] **Refactor** — Replace the sectionless acceptance test's hand-written rationale with the `HEADINGLESS_RATIONALE` harness fixture and assert the rendered node equals that fixture, so the no-heading edge case is proven from the source of truth instead of a duplicated literal.
- [x] **Cleanup** — Correct the two `plan-format` Parsing Rules sentences that still name the reviewer's fallback node `Raw`, restating them as `Untitled` so the permanent spec matches the code that has emitted that label since the Adapter commit, and drop the redundant "raw" adjective beside it.
- [x] **Refactor** — Delete the duplicated `data = cast(ActionData, node.data)` binding in `check_action_logic`, so the value the `results` map consumes is bound once, with the first assignment's discarded evaluation removed.

## Implementation Notes

- **Harness builder splits into fragments, not literals.** `section(title, body)`, `fenced(body, fence)`, `rationale(*blocks)` and `sections(pairs)` compose every fixture, so a scenario states which branch it drives instead of carrying opaque Markdown. `rationale` joins with `\n\n` and blocks carry no trailing newline, which is what keeps exactly one blank line between two sections.
- **Branch shapes stay literal where a helper would obscure them.** `EMPTY_SECTION_RATIONALE`, `DUPLICATE_TITLE_RATIONALE`, `TRAILING_WHITESPACE_HEADING`, `NON_SPLITTING_LINES` and the `unclosed` variant are written out verbatim, because a builder that could emit them cleanly would also hide the very shape the Adapter test asserts on.
- **`HIDDEN_HEADING` is named once** so the `FENCED_HEADING_RATIONALES` parametrization can prove each of the four fence variants (backtick, tilde, longer, unclosed) really carries a `### ` line that a naive splitter would tear apart — the property that makes those fixtures worth having.
- **Red was a real collection failure**, `ModuleNotFoundError: tests.harness.setup.rationale_scenarios`, before the module existed; Green reported 24 passing tests (13 single cases plus the 3-, 4-, and 3-case parametrizations, matching the plan's expectation of 23 plus one more uncovered by the count).
- **The splitter is a line-wise scan carrying one explicit fence state.** A fence opens on three or more backticks or tildes (at most three leading spaces) and closes only on the same character at or above the opening length, which is the single rule covering the backtick, tilde, and four-backtick fixtures. An unclosed fence never clears, so a trailing `### ` line stays inside its own section instead of being torn out.
- **Only a column-zero `### ` splits.** `#### ` and an indented `   ### ` line stay body text, and the title is `strip()`-ed so trailing spaces never reach the label. Splitting on the marker without the column-zero test would have produced two nodes with invalid Markdown bodies.
- **Body trimming is line-level, not `str.strip()`.** `_trim_blank_lines` drops only the blank lines at each end of a block, which preserves an indented first line verbatim and makes a whitespace-only rationale yield no sections at all — the two constraints that rule out a blanket strip.
- **The legacy pair deliberately survives this commit.** `rationale_entries`, `recognized_rationale_sections`, and `ALLOWED_RATIONALE_SECTIONS` are still consumed by `handle_mount_logic` and `test_section_filtering.py`; only their `Raw` wording moved to `Untitled`. Removing them belongs to the Refactor deliverable, where the mount path has already switched.
- **The label rename and its assertion moved together.** The sectionless acceptance test was renamed to `test_tui_renders_sectionless_rationale_as_untitled_node` and asserts `["Untitled"]`, so no commit left the suite red on a stale literal.
- **Evidence:** Red was `ImportError: cannot import name 'rationale_sections'`; Green ran 54 tests across splitter, legacy filtering, harness, and acceptance suites; the scripted insertion left one blank line before the legacy splitter and `ruff format` normalised it; the unfiltered suite ended at 2669 passed / 5 skipped.
- **The mount switch was three guarded replacements.** The import moved from `rationale_entries` to `rationale_sections`, the single call site changed with it, and the fallback comment was restated because "whole-block fallback" no longer describes an entry that only ever holds preamble text. A follow-up grep confirmed `rationale_entries` left the helper module entirely.
- **The quieter styling survived by structure, not by luck.** `rationale_sections` emits a `RATIONALE_FALLBACK_TITLE` entry only while `title is None`, i.e. never after the first heading, so at most one entry can match. The `title == RATIONALE_FALLBACK_TITLE` condition therefore keeps styling exactly one node, which is why the check needed no guard against a second match.
- **The acceptance test became the harness builder's first non-unit consumer.** Its rationale is now composed from `PREAMBLE`, `section(...)`, and `sections(NON_PROTOCOL_SECTIONS)` instead of hand-written Markdown, so the fixture is exercised through the real reviewer boundary and the test carries no shadow copy of `section()`.
- **The replaced test asserted exactly the behaviour being removed.** `test_tui_only_accepts_markdown_headings` expected `["Summary"]` for a rationale whose `### Extra Details` merged into Summary and whose numeric-marker preamble was dropped; the new test proves one node per authored heading plus a leading `Untitled` node for the preamble, and additionally asserts the non-protocol node carries only its own body.
- **The legacy trio deliberately survives this commit.** Production no longer calls `rationale_entries`, `recognized_rationale_sections`, or `ALLOWED_RATIONALE_SECTIONS`, but `test_section_filtering.py` still exercises all three directly. Deleting them without that test would leave the suite red, so the removal is the Refactor deliverable.
- **Evidence:** Red was the acceptance test failing on `['Summary']`; Green ran 54 targeted tests with zero failures; `ruff` reported both touched files already formatted and all checks passed; the unfiltered suite ended at 2669 passed / 5 skipped.
- **The relocation was proven before the pruning.** The `_rationale_content` case ran standalone against the live helper and passed before any production line was deleted, so the moved coverage is verified rather than a pasted copy that might never execute. Relocating and deleting in one unverified step is how a refactor silently drops an assertion.
- **The removal was bounded by two definition anchors.** The deleted span ran from `def recognized_rationale_sections(` to `def on_tree_node_highlighted(`, and the script asserted the span contained `rationale_entries` and did not touch `_rationale_content`. An over-broad anchor therefore failed loudly instead of eating the surviving helper or the detail-view dispatcher.
- **`import re` survives the pruning.** Only the trio's `re.split` and `re.sub` disappeared; `_FENCE_PATTERN = re.compile(...)` keeps the module-level import load-bearing, which is why deleting the legacy splitters raised no unused-import error.
- **`test_section_filtering.py` was deleted, not relaxed.** Every case in it asserted the whitelist filter or the legacy entry shape, so none translated forward. The one behaviour worth keeping — that only a section node carries rationale Markdown — moved into the splitter contract suite as `test_rationale_content_renders_only_section_nodes`.
- **The suite shrink is accounted for.** The unfiltered run fell from 2669 to 2662, a net drop of seven: the superseded file's whitelist cases left and the single relocated case arrived in their place.
- **Evidence:** the relocated test ran 1 passed standalone; the pruning script reported the removed span and the unlink with the trio absent from `src tests`; `ruff check` and `ruff format --check` were clean on both touched files; the targeted suites ran 47 passed; the unfiltered suite ended at 2662 passed / 5 skipped.
- **The invariant kept its name because its surviving claim still earns it.** `rationale_heading_only` still states the one rule that did not move, namely that only a column-zero level-three heading opens a section, so the name stays the anchor any citing prose would use and only the claims changed: every title splits, fences are respected, preamble is preserved, and a heading-less rationale renders as `Untitled`.
- **The docstring described a node shape that no longer exists.** "The whole-block fallback" was written when an unrecognized rationale collapsed into one merged node; after the splitter the `Untitled` entry holds only preamble text or a heading-less rationale, so the wording was restated rather than deleted, because the helper still has a shape worth explaining, just a different one.
- **The styling trade-off is documented instead of silently inherited.** The quieter label keys on the title string equalling `Untitled`, so an author who genuinely writes that heading gets the same quieter styling. Keying on position instead would mis-style a preamble node whenever a heading appears elsewhere in the rationale, so the trade-off is recorded in the invariant as deliberate rather than left to be rediscovered.
- **The stale-reference audit found no third location.** The invariant name appears only in the reviewer page, the retired fallback wording survived only in the docstring this deliverable restated, and the pruned trio plus its superseded test appear nowhere under `src tests`.
- **`RationaleScenarios` joined the Harness map.** The fixture module was load-bearing for the splitter suite, the harness contract suite, and the reviewer acceptance test, yet had no page while every peer in the Test Harness table had one. This deliverable adds `docs/architecture/tests/setup/rationale_scenarios.md` and registers it beside `EditScenarios`, `ContextScenarios`, and `PruningScenarios`, so the documented harness boundary matches the harness that exists.
- **Evidence:** the audit printed one invariant reference and one docstring occurrence; `ruff check` and `ruff format --check` were clean on the logic module; the rationale suites ran 23 passed; the unfiltered suite ended at 2662 passed / 5 skipped, so a prose-only change altered no behaviour.
- **The acceptance file was inconsistent with itself.** Its non-protocol sibling test has driven the harness builder since the Wiring cycle, while the sectionless test kept a hand-written duplicate of a value the harness already composes as `HEADINGLESS_RATIONALE`. The swap removes the file's last shadow literal, so one file no longer proves the same behaviour two ways.
- **The two substring checks were weaker than the equality that replaced them.** `"1. Synthesis" in content` and `"One model call keeps the audit trail tight." in content` would both pass for a node carrying extra or reordered content, and would silently stop matching if the fixture changed — the exact failure mode a shadow copy hides. Comparing the whole node to `HEADINGLESS_RATIONALE` proves it renders the source of truth exactly.
- **The swap could not shift a byte.** The literal and the fixture were byte-identical, and the splitter trims only the blank lines at each body's edges, so no trailing-newline difference could appear between the composed fixture and the rendered node. That is why the equality held on the first run rather than needing normalisation.
- **A test-only refactor changed no count.** The acceptance file ran 3 passed, `ruff check` reported all checks passed with the file already formatted, and the unfiltered suite ended at 2662 passed / 5 skipped — the same figure as before, which is the evidence that only the assertion's strictness moved.
- **Evidence:** the targeted acceptance run reported 3 passed; the style gate was clean; the unfiltered suite ended at 2662 passed / 5 skipped.
- **A spec is prescriptive, so a retired label is a defect there, not history.** The slice's own Context section narrates the pre-change state by design and the release note is a dated record, so both keep their `Raw` wording; `plan-format.md` states what the format *is*, so naming a node the reviewer no longer emits would misdirect whoever reads it as the system invariant.
- **The guard inspected the file before rewriting it.** Two backticked `Raw` tokens and one `entire raw content` phrase were counted first, so a spec that had drifted during this session's twenty remote commits would abort the script instead of taking a blind replacement across the wrong sentences.
- **Only the label and one adjective moved.** The paragraph already described the fence-aware behaviour correctly, namely that the reviewer opens a node for every `###` heading it finds and that fenced lines, `####` lines, and numeric markers stay body text, so the correction restated the two fallback sentences and turned "its entire raw content" into "its entire content", which no longer reads oddly beside `Untitled`.
- **`grep -c` under-reports the replacement.** It counts matching *lines*, and both replaced tokens sit on line 99, so the count reads `1` while the sentence now names `Untitled` twice. A later audit should read the sentence rather than trust that number.
- **Nothing pinned the prose.** The only `plan-format` reference under `src tests` is a pointer in `plan_builder.py` that names the document without parsing its wording, so the correction needed no test, and a suite that stayed at 2662 passed / 5 skipped is the evidence it altered no behaviour.
- **The dated release note keeps its wording deliberately.** `docs/project/releases/v0.2.3.md` shipped `Raw` as a user-visible outcome of that version, so rewriting it would falsify a historical record while fixing nothing, which is the opposite judgement from a prescriptive spec.
- **Evidence:** the audit printed the paragraph with two backticked `Raw` tokens and found no spec-reading test; the script printed the corrected sentence; the retired-label sweep returned only the release note and the slice's own narration; the style and full-suite gates were outside this prose-only change, and the unfiltered suite ended at 2662 passed / 5 skipped.
- **The duplicate was real, not a stale dump.** A commit had landed since the session snapshot was taken, so the find was re-run against the live file: lines 329 and 331 still carried the same cast, the second followed immediately by the `results` map. Deleting the first binding therefore removed an evaluation whose value nothing ever read, and the `isinstance` guard above it already narrowed `node.data`, so the surviving cast is a typing restatement rather than a check.
- **The targeted run's failure was a Local Flaw, not a regression.** `git grep -l 'check_action_logic' -- tests` matched nothing, exited 1, and — as the left side of a `;` assignment — aborted the chain before pytest ran. No application code outside the deliverable was implicated, so the fix was to re-run the integration gate with a guarded probe instead of re-partitioning the slice.
- **"No test names the gate" is not "the gate is untested."** `check_action_logic` is reached indirectly: `ReviewerApp.check_action` delegates to it, and `test_reviewer_app_modifications.py` asserts the `revert` binding resolves `False` then `True` as the action's `modified` state changes, which is the `results` map the prune left untouched. Recording this stops a later reader from treating the unmatched grep as evidence of dead code.
- **The suite count is the neutral-behaviour proof.** The unfiltered run ended at 2662 passed / 5 skipped, identical to before the prune, so no test could differentiate the two bindings — the expected outcome for an expression whose value was immediately overwritten by an identical one.
- **The As-Built pass needed a judgement, not an edit.** The slice's Impact section names the reviewer component page, and that page documents invariants rather than internal statement counts; none described how often the action gate casts its node data, so the page keeps its text. Documenting a deleted redundant line would record an implementation detail no caller can observe.
- **Evidence:** the pre-edit probe printed the two assignment lines and no direct test reference; the post-edit probe printed `1` binding with the `results` map following it; `ruff check` and `ruff format --check` were clean on the logic module; the coverage probe printed the delegation at `textual_plan_reviewer_app.py:160`, the assertions at `test_reviewer_app_modifications.py:49,52`, and four logic-module importers; the unfiltered suite ended at 2662 passed / 5 skipped.
- **The Rule Ratchet was considered and declined, deliberately.** The duplicate binding was one merge artifact inside a file this slice rewrote, not a recurring anti-pattern or a boundary leak, and no rule family can flag a re-bound identical expression without also flagging legitimate reassignment, so a rule invented around a single occurrence would add noise instead of protection. Recording the judgement keeps a later reader from treating its absence as an oversight.
- **The milestone effect is bounded to one checkbox.** This completion ticks `04-10-rationale-sections` only: milestone 4 keeps its `IN PROGRESS` status and its `PROJECT.md` roadmap row, because 04-06, 04-07, 04-08, 04-09, 04-11, and 04-12 remain open. The reviewer's component page likewise stays `Refactoring` for the same reason, so no status edit outside the tick is correct here.
- **Evidence:** the completion probe printed the slice at `Completed` with eight checked deliverables, the milestone tick with its status header unchanged, and `NONE` for the pruned trio, the whitelist filter, and a live `Raw` label; the unfiltered suite ended at 2662 passed / 5 skipped.

## Verification
1. **Non-protocol section:**
   Write a plan whose rationale carries a `### Trade-offs` heading, start a session, and inspect the tree.
   Verify Rationale lists Trade-offs as its own node.
2. **Fenced heading:**
   Embed a fenced block containing `### ` inside Notes and inspect the tree.
   Verify the section count is unchanged.
3. **Preamble:**
   Put a paragraph before the first heading and inspect the tree.
   Verify a quieter Untitled node appears first.
