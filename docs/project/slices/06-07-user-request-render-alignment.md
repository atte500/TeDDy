# Slice: `## User Request` Render Alignment and the Missing Lifecycle Page
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** [06-01-literal-helper-single-sourcing](./06-01-literal-helper-single-sourcing.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [MarkdownReportFormatter](/docs/architecture/core/services/markdown_report_formatter.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [SessionService](/docs/architecture/core/services/session_service.md)
- **Scope Slug:** `user-request-render-alignment`

## Goal
Make the two producers of the `## User Request` block emit identical bytes for identical input, so a report renders the same whether it was assembled from a template or appended to an existing file, and give the component that owns the append path the contract page it currently lacks.

## Context
- Both producers already route the message body through the shared `embed_in_fence` primitive, so fence mechanics are single-sourced. The bytes around the block are not: `MarkdownReportFormatter` rstrips every rendered line before its fence-tracking loop (`markdown_report_formatter.py:103`), so fenced content loses per-line trailing whitespace on the template path, while `SessionLifecycleManager._append_user_request` writes the message with no sanitizer pass at all.
- The sanitizer also toggles its in-fence state on a line whose stripped text begins with a fence run rather than comparing fence width, so a widened wrapper that itself contains a fence line flips the state and lets the blank-line collapsing rules run inside the block.
- The language tag is a deliberate product decision: both producers should emit a bare fence with an empty tag instead of `text`, matching `## User Reply`, which already does. `docs/project/specs/report-format.md` does not describe this section and does not pin the tag, so no spec change is required — but the change touches `execution_report.md.j2`, `_append_user_request`, and every byte-exact assertion that hardcodes a `text`-tagged block across the unit and acceptance suites.
- This is the one behavior-changing item in the milestone, recorded as an explicit product decision on 2026-11-06. Everything else in Milestone 6 preserves runtime behaviour.
- The same component owns the presence-gated resume prompts (`_can_prompt_user`, `_resolve_blank_message`) and the pipeline pass-through across the COMPLETE_TURN delegation, and has no component design document, so the CLI adapter, `SessionOrchestrator`, `ConsoleInteractor`, and `ISystemEnvironment` pages each reference behaviour with no page to link to.
- Dead parameter: `SessionLifecycleManager.trigger_replan` still accepts `original_plan_content`, whose last consumer disappeared when the internal `trigger_replan_turn` call stopped passing it. Every `trigger_replan` call site in `session_orchestrator.py` must stop supplying it in the same commit.
- Ordering: [06-01](./06-01-literal-helper-single-sourcing.md) single-sources the heading first, so this slice changes the bytes of a block whose heading already has one definition.

## Scenarios

> As a maintainer, I want the same message to render the same bytes on both paths.

```gherkin
Given a message containing trailing whitespace and a blank line
When it is rendered through the template and appended to an existing report
Then both produced blocks are byte-identical
```

> As a reader, I want the user's request fenced without a language tag.

```gherkin
Given any turn's report
When the User Request block renders
Then its fence carries no language tag
And it matches the User Reply block's convention
```

> As a maintainer, I want the lifecycle manager's contract documented.

```gherkin
Given the four component pages that reference presence-gated resume prompts
When the new lifecycle page exists
Then each reference links to it
And the page states the presence gates, the pipeline pass-through, and the append path's invariants
```

## Edge Cases
- **Trailing whitespace**: If the template path rstrips fenced lines, then it stops rstripping inside a fence, because trailing whitespace is content inside a code block and the two paths must agree.
- **Fence width**: If the tracker compares fence width, then a four-backtick wrapper containing a three-backtick line stays in-fence, because width comparison is the only rule that survives nesting.
- **Bare fence and the preservation regex**: If the heading is now single-sourced, then the regex is derived from it, so this slice's byte change cannot silently break turn preservation.
- **Append path sanitization**: If the append path gains the sanitizer, then it gains it from the same shared primitive the template uses, because a second sanitizer implementation reintroduces the divergence.
- **CRLF**: If a message arrives with CRLF, then both paths normalize identically, because byte-exact assertions run on both platforms in the CI matrix.
- **Assertion churn**: If dozens of tests pin a `text`-tagged block, then they are enumerated and converted tests-first, because a bulk find-and-replace across assertions hides the ones that were pinning something else.
- **Observer independence**: If a report observer parses the section, then it tolerates a missing language tag, because the parser must describe the format rather than the reverse.
- **Dead parameter**: If `original_plan_content` is removed, then every call site stops supplying it in the same commit, because a keyword left at one site is a `TypeError` at the first turn that replans.
- **Product change boundary**: If another item in this milestone needs the sanitizer's behaviour, then it adopts this one rather than keeping a local copy, because the milestone's no-new-behaviour rule has exactly one documented exception and this is it.
- **Pipeline pass-through**: If the lifecycle page documents the COMPLETE_TURN delegation, then it states that a pipeline run never prompts, because that pass-through is the reason the page is worth writing.

## Key Unknowns
- [ ] [Technical] How many byte-exact assertions pin a `text`-tagged User Request block. Design Sensitivity: if they concentrate in a shared observer or a single report fixture → the change is one edit and the churn is trivial; if they are scattered across unit and acceptance modules → the slice enumerates them tests-first and converts them before touching the template, because a mixed state cannot be distinguished from a regression.

## Impact
1. `[MIGRATE]` `src/teddy_executor/resources/templates/execution_report.md.j2` — the User Request block's fence loses its language tag.
2. `[MIGRATE]` `SessionLifecycleManager._append_user_request` — routes through the shared sanitizer and emits the same bare fence.
3. `[MIGRATE]` The report sanitizer's fence tracker — compares fence width instead of testing a stripped prefix.
4. `[MIGRATE]` `MarkdownReportFormatter` — stops rstripping lines inside a fence.
5. `[NEW]` `docs/architecture/core/services/session_lifecycle_manager.md` following the component-design template.
6. `[MIGRATE]` The Component Map — a `SessionLifecycleManager` row linking the new page.
7. `[PRUNE]` `SessionLifecycleManager.trigger_replan`'s `original_plan_content` parameter and every call site supplying it.
8. `[MIGRATE]` The byte-exact assertions across the unit and acceptance suites that pin the old tag, plus the report observer if it parses this section.

## Deliverables
- [ ] **Interface** — Write the lifecycle-manager page (purpose, consumers, constructor-injected dependencies, presence gates, append-path invariants) and add its Component Map row.
- [ ] **Harness** — Add the parity test: the same message rendered through both paths produces identical bytes.
- [ ] **Core** — Align the sanitizer's fence tracking, stop the template path's in-fence rstripping, and convert the assertions tests-first.
- [ ] **Migration** — Switch both producers to the bare fence and remove the dead `trigger_replan` parameter with its call sites.
- [ ] **Cleanup** — Link the four consumer pages to the new lifecycle page, and confirm the preservation regex still matches after the heading change.

## Implementation Notes

## Verification
1. **Parity:**
   Run the new parity test with a message containing trailing whitespace and a blank line.
   Verify both paths produce byte-identical blocks.
2. **Tag:**
   Run one acceptance test and inspect the rendered report.
   Verify the User Request fence carries no language tag and matches User Reply.
3. **Dead parameter:**
   Run `git grep -n "original_plan_content" -- src`.
   Verify no hit remains.
