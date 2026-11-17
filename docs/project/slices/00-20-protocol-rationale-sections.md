# Slice: Rationale Section Consolidation
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** N/A
- **Specs:** [Plan Format](/docs/project/specs/plan-format.md), [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `rationale-sections`

## Goal
Deliver a four-section rationale contract — `Summary`, `Expectation`, `Progress`, `Notes` — whose wording is locked in the MRP and whose sections render as navigable nodes in the plan reviewer.

## Context
- `MarkdownPlanParser`: carries the rationale as one opaque string. No parser or domain-model change is required.
- `ALLOWED_RATIONALE_SECTIONS`: gates node creation in `textual_plan_reviewer_helpers.py`. A title outside the list is appended to the previous node's content.
- `MarkdownPlanBuilder`: emits the old `1. Synthesis` through `4. State Dashboard` default, so the shared harness must move with the protocol.
- `plan-format.md`: pins the rationale shape and still teaches `Expected Outcome` plus the deprecated `PROMPT`/`INVOKE` actions in its comprehensive example.
- `debugger.md`: names a workflow step `Synthesis Presentation`; it must become `Summary Presentation` so one concept keeps one word.
- Exact drift inventory, re-derived across the tree: `plan-format.md` lines 67 and 72–81 (the rationale format) plus 235–244 (the comprehensive example, which also teaches the deprecated `PROMPT`/`INVOKE`); `debugger.md:78` (`Synthesis Presentation`); `README.md:84` (the "synthesis, justification, and expected outcomes" sentence); and `tests/harness/drivers/plan_builder.py` lines 218–227 (the default rationale). Twelve test modules carry the old titles: `test_tui_instruction_bridge.py`, `test_tui_rationale_parsing.py`, `test_tui_rationale_scrolling.py`, `test_resilient_edit_matching_integration.py`, `test_validation_diagnostics_integration.py`, `test_rationale_filtering.py`, `test_section_filtering.py`, `test_markdown_plan_parser_session.py`, `test_normalize_h1.py`, `test_parser_create_overwrite.py`, `test_parser_path_retention.py`, and `test_plan_builder.py`.
- `test_section_filtering.py` asserts the legacy allowlist names on purpose, so it is not drift: leave its `Synthesis`, `Justification`, and `State Dashboard` entries in place. `test_rationale_filtering.py` exercises legacy-section rendering, so keep a legacy case and add the new titles beside it rather than replacing them.
- `interactive-session-workflow.md` carries no rationale section names and needs no change.
- `plan-format.md`'s `Expected Outcome` mentions at lines 174 and 189 are the `EXECUTE` parameter covered elsewhere in the spec, not rationale vocabulary; leave them untouched.
- The MRP wording is already updated in this slice. The remaining work synchronizes the spec, harness, prompt vocabulary, tests, and the stale README sentence.
- The MRP `## Response Format` was consolidated while this slice was open: `No Preamble` and `Response Termination` merged into `Response Boundaries`; `Rationale Encapsulation` absorbed into a single `Code Block Formatting` whose nesting rule wins over the old "exactly 4" wording; `Progress and Notes` deleted in favor of the `### Structure` template; and the Action Plan/Message exclusivity rule moved beneath that template.
- `plan-format.md`'s *Code Block Nesting* section still speaks only of backticks and pins a fence strictly greater than the longest backtick run, while the MRP now admits tilde fences under the same nesting rule. The two must agree before the spec can be called aligned.

## Scenarios
> As a plan reviewer, I want the rationale tree to expose Summary, Expectation, Progress, and Notes as separate nodes so that I can move through the whole story without scrolling a single blob.

```gherkin
Given a plan whose rationale uses the four protocol sections
When the plan reviewer builds the Rationale tree
Then the tree shows Summary, Expectation, Progress, and Notes as sibling nodes
And each node contains only its own section content
```

## Edge Cases
- **Legacy rationale**: If a resumed session stores `Synthesis`, `Justification`, or `State Dashboard`, then those titles still create nodes, because the allowlist keeps the legacy names alongside the new ones.
- **Unknown heading**: If a rationale contains an unrecognized `###` title after a recognized section, then its content remains appended to the previous node, preserving the current fallback behavior.
- **Missing expectation**: If a plan omits `Expectation`, then the Status binding loses its anchor, so the protocol test must fail the slice.
- **Summary scope**: If `Summary` only recaps the previous turn, then the section violates the protocol requirement to carry the whole session story.

## Key Unknowns
No open unknowns. The protocol wording is locked by the MRP; remaining work is mechanical synchronization.

Resolved during discovery:
- [x] `[Domain]` Section names and semantics: Resolved by the locked MRP wording. Design Sensitivity: fixed names become the TUI allowlist and spec vocabulary.
- [x] `[Technical]` Parser impact: Resolved by static reading. The rationale is opaque text, so no parser change is required.
- [x] `[Functional]` TUI rendering: Resolved by the existing splitter. Recognized titles become nodes; unknown titles merge into the previous node.

## Impact
1. `[EXTEND]` `MRP.md` — Replace Synthesis/Justification/Expectation/State Dashboard with Summary/Expectation/Progress/Notes and define Summary as the whole session story.
2. `[EXTEND]` `ALLOWED_RATIONALE_SECTIONS` — Add the four new titles while retaining the legacy titles for resumed plans.
3. `[MIGRATE]` `MarkdownPlanBuilder` and affected tests — Move fixtures and assertions to the new default rationale.
4. `[MIGRATE]` `plan-format.md` — Align the rationale format, replace the stale deprecated example actions, and reconcile *Code Block Nesting* with the MRP's tilde-and-backtick rule.
5. `[MIGRATE]` `debugger.md` — Rename `Synthesis Presentation` to `Summary Presentation`.
6. `[PRUNE]` Obsolete `Expected Outcome` rationale references — Remove the duplicate section name after migration. The legacy reviewer titles are retained deliberately, so they are not pruned.

## Deliverables
- [x] **Interface** - Lock the MRP rationale contract and extend `ALLOWED_RATIONALE_SECTIONS` additively. Landed in `f6126669` (four-section contract, additive allowlist, exact-list test) and consolidated in `e6631ed9` and `012e2f17`.
- [x] **Harness** - Update `MarkdownPlanBuilder` to emit Summary, Expectation, Progress, and Notes. Landed with its two default-binding test modules in one commit.
- [ ] **Migration** - Update `plan-format.md`, `debugger.md`, the stale README sentence about synthesis/justification/expected outcomes, and every test fixture that pins the old rationale titles. Reconcile `plan-format.md`'s *Code Block Nesting* section with the MRP's tilde-and-backtick nesting rule.
- [ ] **Cleanup** - Remove obsolete `Expected Outcome` rationale references and keep legacy reviewer titles intentionally.

## Implementation Notes
- The protocol text, the allowlist extension, and the exact-list test landed together in `f6126669`, so the atomic-commit constraint is discharged for those files. An unrecognized first section is dropped because `current_node` starts as `None`, so `MRP.md` must never be changed in a way that removes a title the allowlist accepts. The remaining spec, harness, fixture, prompt, and README changes may move in TDD-sized steps as long as `make test` stays green.
- `Summary` synthesizes the entire session story, not just the previous turn.
- Keep `Synthesis`, `Justification`, and `State Dashboard` in the reviewer allowlist so resumed sessions still render stored plans.
- The MRP action catalogs show the boolean toggles as `[true|false]` placeholders by an explicit product decision, while `plan-format.md` still states the emitted value MUST be enclosed in backticks. Reconcile the wording or confirm the placeholders are notation-only when aligning the spec.
- The Harness flip moved as one commit with the two modules that bind the builder's default: `MarkdownPlanBuilder` now emits `### Summary`, `### Expectation`, `### Progress`, and `### Notes`, and `test_plan_builder.py` plus `test_tui_rationale_parsing.py` follow it. The mixed-format acceptance case now injects its own legacy-plus-protocol rationale through `with_rationale` instead of post-processing the default, so it still pins mixed-heading parsing without binding the builder. Because `Expected Outcome` is not an allowlist title, a stored legacy rationale renders that section's content inside the preceding node rather than dropping it.

## Verification
1. **Protocol wording:**
   Run `teddy get-prompt pathfinder`.
   Verify the response protocol contains `### Summary`, `### Expectation`, `### Progress`, and `### Notes`.
2. **Reviewer rendering:**
   Start `teddy start` with a plan using the four sections.
   Open the Rationale tree.
   Confirm four sibling nodes appear and each opens its own content.
3. **Legacy rendering:**
   Resume a session whose stored plan uses `Synthesis`, `Justification`, `Expectation`, and `State Dashboard`.
   Open the Rationale tree.
   Confirm the legacy sections still render.
