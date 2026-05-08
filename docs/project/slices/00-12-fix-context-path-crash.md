# Slice: Fix Context Path Crash
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:**
  - [ContextService](../../architecture/core/services/context_service.md)

## Business Goal
Fix the catastrophic crash where `teddy` attempts to read a descriptive text block as a file path during context gathering.

## Scenarios
> As a user running `teddy start`, I want the system to gather context without crashing even if spec files are included in the context list.
```gherkin
Given a project with a spec file containing a long description
And that spec file is listed in .teddy/context
When I run "teddy start"
Then the command completes successfully without a "File name too long" error
```

## Deliverables
- [ ] **Logic** - Identify and fix the logic leak in `ContextService` that treats file content as paths.
- [ ] **Wiring** - Verify the fix with a regression test.

## Implementation Notes

## Delta Analysis

## Guidelines for Implementation
