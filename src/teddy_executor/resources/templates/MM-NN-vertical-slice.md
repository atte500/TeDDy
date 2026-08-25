# Slice: {{feature_name}}
- **Status:** [Planned | In Progress | Completed]
- **Milestone:** [link]
- **Specs:** [links]
- **Prototype:** [link]
- **Component Docs:** [links]
- **Scope Slug:** `feature-slug`

## Business Goal

**Format:** 1-2 sentences describing the value delivered by completing this slice.
The business value or user need this slice addresses.

## Scenarios

**Format:** Gherkin syntax with Given/When/Then. One scenario per happy-path behavior.
> As a [user type], I want to [action] so that [benefit].

```gherkin
Given [precondition]
When [action]
Then [expected outcome]
```

## Edge Cases

**Format:** Bulleted list. Each entry starts with a bold title, then describes the condition and expected behavior.
- **Title**: If [condition], then [behavior], in order to / because [reason/goal].

## Key Unknowns

**Format:** Checklist of unresolved risks. Tags: `[Technical]` for code/architecture, `[Functional]` for behavior/UX. Mark as `[x]` when resolved.
- [ ] [Tag] Title: Description of the unknown.

## Implementation Plan

**Format:** Paragraphs describing the technical approach, key decisions, and dependencies.
Summary of changes required to integrate the feature, combined with the actionable strategy and guidelines.

## Deliverables

**Format:** Checklist of deliverables. Types include: Contract, Logic, Wiring, Harness, Refactor, Cleanup, Migration. Each deliverable is one atomic unit of work.
- [ ] **Type** - Description.

## Implementation Notes

**Format:** Free-form notes recording decisions, rationale, and deviations from the original plan during implementation.
Filled by the Developer as things get implemented.

## Verification

**Format:** Numbered checklist. Each entry describes a test to run or a behavior to verify manually.
Checklist of manual smoke-test scenarios that the Developer executes before marking the slice as Complete.
