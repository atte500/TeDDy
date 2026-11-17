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
- The MRP wording is already updated in this slice. The remaining work synchronizes the spec, harness, reviewer allowlist, prompt vocabulary, and tests.

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
4. `[MIGRATE]` `plan-format.md` — Align the rationale format and replace the stale deprecated example actions.
5. `[MIGRATE]` `debugger.md` — Rename `Synthesis Presentation` to `Summary Presentation`.
6. `[PRUNE]` Obsolete `Expected Outcome` rationale references — Remove the duplicate section name after migration. The legacy reviewer titles are retained deliberately, so they are not pruned.

## Deliverables
- [ ] **Interface** - Lock the MRP rationale contract and extend `ALLOWED_RATIONALE_SECTIONS` additively.
- [ ] **Harness** - Update `MarkdownPlanBuilder` to emit Summary, Expectation, Progress, and Notes.
- [ ] **Migration** - Update `plan-format.md`, `debugger.md`, and every test fixture that pins the old rationale titles.
- [ ] **Cleanup** - Remove obsolete `Expected Outcome` rationale references and keep legacy reviewer titles intentionally.

## Implementation Notes
- The protocol text, spec, allowlist, harness, prompt rename, and affected tests MUST land in one atomic commit. An unrecognized first section is dropped because `current_node` starts as `None`, so an MRP-only change blanks the Rationale pane.
- `Summary` synthesizes the entire session story, not just the previous turn.
- Keep `Synthesis`, `Justification`, and `State Dashboard` in the reviewer allowlist so resumed sessions still render stored plans.

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
