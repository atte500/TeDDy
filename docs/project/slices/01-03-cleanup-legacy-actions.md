# Slice: 01-03-Cleanup Legacy Actions

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md)
- **Component Docs:** [docs/architecture/core/services/markdown_plan_parser.md](/docs/architecture/core/services/markdown_plan_parser.md)

## Business Goal
Remove deprecated legacy actions (`PROMPT`, `INVOKE`, `RETURN`, `PRUNE`) from the core protocol to finalize the transition to the Structural Message Protocol and reduce codebase complexity.

## Scenarios
> As a Developer, I want the parser to reject legacy actions so that I am forced to use the modern protocol.

```gherkin
Given a plan containing a "### PROMPT" or "### INVOKE" action
When the plan is parsed
Then an "InvalidPlanError" is raised detailing that the action is no longer supported
```

## Edge Cases
- **Mixed Protocols**: If a plan uses `## Message` but also includes a legacy action in the `## Action Plan` (if present), the parser must fail during structural validation or action dispatch resolution.

## Deliverables
- [ ] **Cleanup** - Remove `PROMPT`, `INVOKE`, `RETURN`, `PRUNE` from `ActionType` enum in `src/teddy_executor/core/domain/models/plan.py`.
- [ ] **Cleanup** - Remove legacy properties (`is_legacy`, `is_terminal` updates) from `ActionData`.
- [ ] **Cleanup** - Remove parsing logic for legacy actions from `MarkdownPlanParser`.
- [ ] **Cleanup** - Remove deprecated strategy functions in `src/teddy_executor/core/services/action_parser_complex.py`.
- [ ] **Cleanup** - Remove deprecation warning logic from `ExecutionOrchestrator`.
- [ ] **Cleanup** - Prune `PRUNE` validation logic and any remaining legacy validators.
- [ ] **Migration** - Update all internal tests to use `## Message` instead of legacy communication actions.
- [ ] **Wiring** - Final validation check to ensure no references to legacy actions remain in production code.

## Implementation Notes
*(To be populated during implementation)*
