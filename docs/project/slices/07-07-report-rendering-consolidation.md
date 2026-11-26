# Slice: Report Rendering Consolidation
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** [06-07-user-request-render-alignment](./06-07-user-request-render-alignment.md)
- **Specs:** [Report Format](/docs/project/specs/report-format.md)
- **Prototype:** None
- **Component Docs:** [MarkdownReportFormatter](/docs/architecture/core/services/markdown_report_formatter.md), [ExecutionReport](/docs/architecture/core/domain/execution_report.md), [ReportParser](/docs/architecture/tests/observers/report_parser.md)
- **Scope Slug:** `report-rendering-consolidation`

## Goal
Render `## Resource Contents` from one classification pass instead of two, and teach the report observer to read inline fenced blocks, so the template cannot disagree with itself and the harness can assert on what the report actually contains instead of falling back to raw regex.

## Context
- `execution_report.md.j2` renders `## Resource Contents` from two separate sites. Two sites for one section is the report-format analogue of the literal duplication Milestone 6 removes: the second site exists because a resource can arrive through two paths, and the fix is to classify once and render once.
- The dependency on [06-07](./06-07-user-request-render-alignment.md) is hard. That slice changes the `## User Request` fence and the sanitizer's fence tracking in the same template, and it converts the byte-exact assertions that pin the old tag. Doing both in parallel would mean two migrations of the same test surface.
- The observer gap is what makes the duplication expensive to detect. `tests/harness/observers/report_parser.py` cannot extract inline fenced content, so tests that need to assert on a rendered resource block reach for raw regex over the report string. That is the harness equivalent of a reader parsing a document by eye: it works until the bytes change, and then it fails for a reason unrelated to the behaviour under test.
- What must not change: the rendered bytes of any report whose content is already classified correctly. This slice is a structural consolidation, not a format change, and the existing byte-exact assertions are the proof.
- Boundary note: the observer is a test double in the harness, so improving it is not production work. It belongs here because the render consolidation is only verifiable once the observer can see fenced content structurally.
- Ordering against [06-01](./06-01-literal-helper-single-sourcing.md): the section heading is single-sourced there, so this slice classifies against a constant rather than a literal.

## Scenarios

> As a maintainer, I want one place in the template that decides a resource's section.

```gherkin
Given a report containing resources that arrive through both existing paths
When it renders
Then one classification pass assigns each resource its section
And no second site in the template re-decides
```

> As a maintainer, I want the observer to read the report structurally.

```gherkin
Given a rendered report containing an inline fenced resource block
When the observer parses it
Then the block's content and fence metadata are available as structured values
And no test needs a raw regex to assert on it
```

> As a maintainer, I want a format regression to fail one assertion, not five.

```gherkin
Given a change to the resource block's rendering
When the suite runs
Then the failure names the observer method that mismatched
And it is not five separate byte comparisons in five modules
```

## Edge Cases
- **Resources arriving by both paths**: If the same resource is reachable through both existing paths, then classification deduplicates by path rather than rendering twice, because a duplicated section is what two sites produce when they disagree.
- **Fence inside content**: If a resource body itself contains a fence, then the observer matches on fence width, not on a stripped prefix, mirroring [06-07](./06-07-user-request-render-alignment.md)'s rule so the two do not diverge.
- **Empty section**: If no resources are classified, then the section is omitted entirely rather than rendered empty, preserving today's bytes.
- **Ordering**: If resources are classified from a set, then rendering orders them deterministically, because a report whose section order depends on dict iteration is untestable byte-for-byte.
- **Observer tolerance**: If an older report lacks fenced metadata, then the observer reports the block without it rather than raising, because the observer must describe the format rather than enforce the newest one.
- **Byte parity**: If any existing byte-exact assertion changes, then either the consolidation changed behaviour (a defect) or the assertion pinned a duplicated artefact (which the observer migration removes); the two cases are distinguished before any assertion is edited.
- **Truncated content**: If a resource body is capped for display, then the observer sees the truncation marker as part of the block rather than a shorter body, because a silently shorter body is a wrong assertion waiting to happen.
- **Template macro reuse**: If the section is rendered by a shared macro, then the macro takes the classified groups rather than re-deriving them, because a macro that re-classifies is the second site with a new name.

## Key Unknowns
- [ ] [Technical] How many tests assert on resource blocks through raw regex today. Design Sensitivity: if they concentrate in a handful of observer-driven modules → the migration is one observer method plus those call sites, and the slice stays small; if they are scattered across acceptance and unit suites → the slice converts them tests-first behind the new observer method before the template changes, because a mixed state cannot distinguish a rendering regression from an incomplete migration.

## Impact
1. `[MIGRATE]` `execution_report.md.j2` — one classification pass renders `## Resource Contents`, with deduplication by path and deterministic ordering.
2. `[NEW]` `ReportParser` support for inline fenced content blocks, returning the body and fence metadata as structured values.
3. `[MIGRATE]` The tests asserting on resource blocks — converted to the observer method, with any raw-regex fallback deleted.
4. `[MIGRATE]` `MarkdownReportFormatter`, `ExecutionReport`, and `ReportParser` pages — record the single classification site and the observer's fenced-block contract.
5. `[MIGRATE]` `docs/project/specs/report-format.md` — only if the consolidation exposes an unspecified ordering rule; the format itself does not change.

## Deliverables
- [ ] **Harness** — Add the observer's fenced-block extraction with its fence-width rule and its tolerance for reports lacking metadata.
- [ ] **Migration** — Convert the raw-regex assertions tests-first, so the template change is watched by a structural assertion when it lands.
- [ ] **Core** — Collapse the two render sites into one classification pass, with deduplication and deterministic ordering.
- [ ] **Cleanup** — Record the single classification site and the observer contract on the three pages, and confirm byte parity for every recorded report fixture.

## Implementation Notes

## Verification
1. **Single site:**
   Run `git grep -n "Resource Contents" -- src/teddy_executor/resources/templates`.
   Verify only one render site remains.
2. **Observer structural:**
   Parse a report containing an inline fenced resource block.
   Verify the body and fence metadata come back as structured values.
3. **Byte parity:**
   Render the recorded report fixtures before and after the change and compare.
   Verify identical bytes for every fixture.
