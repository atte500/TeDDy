<!--
Destination: docs/project/milestones/MM-{milestone-slug}.md
Naming: MM = Sequential Milestone Number (e.g. 01, 02).
-->

# Milestone: {{Milestone Title}}
- **Status:** [Planned | In Progress | Completed]
- **Depends On:** [None | links]
- **Specs:** [links]

## Motivation
The Why: Problem definition, customer motivation, and measurable value delivered by this milestone.

## Requirements
The What: Functional and technical capabilities required to deliver the motivation.
1. **Requirement 1:** Description of capability or outcome.
2. **Requirement 2:** Description of capability or outcome.

## Constraints
Technical limitations, architectural boundaries, cross-slice dependencies, or explicit non-goals.
- **Constraint 1:** Description of boundary or exclusion.

## Slices
Split broad requirements across all layers into small, orthogonal vertical slices, each delivering independently verifiable, composable, and extensible functionality. List one unbolded checkbox per slice, and check a box `[x]` only once the slice document records `Status: Completed`; the milestone is complete when every box is checked.
- [ ] [MM-01-slice-slug](../slices/MM-01-slice-slug.md): Minimal standalone end-to-end path.
- [ ] [MM-02-slice-slug](../slices/MM-02-slice-slug.md): Independent capability.
- [ ] [MM-03-slice-slug](../slices/MM-03-slice-slug.md): Extension building on MM-01.
