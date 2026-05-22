# Slice: Fix Validation Context Reset

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow.md](../../specs/interactive-session-workflow.md)

## Business Goal
Ensure that conversation history (previous turns) is preserved when a plan fails validation and an automated replan is triggered.

## Scenarios
> As a user in a session, I want the AI to remember my previous turns even if it makes a validation error, so that I don't have to repeat myself.

```gherkin
Given a session at Turn 2
And Turn 1 is documented in the session history
When the Turn 2 plan fails logical validation
Then the automated replanning turn must include Turn 1 history in its context
And the token count should reflect the accumulated history
```

## Deliverables
- [x] **Logic** - Implement defensive context resolution in `PlanningService.generate_plan`.
- [x] **Cleanup** - Remove redundant context resolution from `SessionPlanner` if it now duplicates `PlanningService` logic.

## Implementation Notes
- **Defensive Resolution**: Updated `PlanningService.generate_plan` to check if `context_files` is `None`. If it is, and a `turn_dir` is provided, the service now calls `self._session_manager.resolve_context_paths` to find the standard `session.context` and `turn.context` manifests.
- **Redundancy Cleanup**: Removed manual context construction from `SessionPlanner`. It now delegates resolution to the planning service.
- **Verification**: Added `test_generate_plan_auto_resolves_context_from_turn_dir_when_missing` to `test_planning_service.py` and delegation test to `test_session_planner.py`. Verified that global history (774 tests) remains stable.

## Implementation Plan
1. Update `PlanningService.generate_plan` to check for `context_files is None`.
2. If `None` and `turn_dir` is present, call `self._session_manager.resolve_context_paths(plan_path)` (constructing a dummy plan path).
3. Verify via existing acceptance tests for session replanning.
