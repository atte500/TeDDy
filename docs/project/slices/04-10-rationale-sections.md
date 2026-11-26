# Slice: Rationale Sections as Authored
- **Status:** In Progress
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
- [ ] **Refactor** — Delete `ALLOWED_RATIONALE_SECTIONS`, `recognized_rationale_sections`, and `rationale_entries`, move `_rationale_content`'s surviving coverage into `test_rationale_sections.py`, and delete `test_section_filtering.py`, keeping the suite green throughout.
- [ ] **Cleanup** — Restate the `rationale_heading_only` invariant in the reviewer component page as the new fence-aware rule, with `Untitled` as the fallback label.

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
