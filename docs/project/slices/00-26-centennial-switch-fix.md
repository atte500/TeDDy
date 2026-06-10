# Slice: Centennial Turn Switch – Session Name Propagation

- **Status:** Draft
- **Type:** Bugfix
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Session Migration Spec](/docs/project/specs/stability-and-bugfixes.md#session-migration) (if applicable)
- **Prototype:** [Shadow Verification](/spikes/debug/21-shadow-loop-fix.py)
- **Component Docs:** [SessionCLIHandlers](/docs/architecture/adapters/inbound/cli.md), [SessionLifecycleManager](/docs/architecture/core/services/session_lifecycle_manager.md), [IRunPlanUseCase](/docs/architecture/core/ports/inbound/run_plan_use_case.md)

## Business Goal

Prevent the session loop from re-processing the continuation session's first turn after a centennial migration. Currently, `_orchestrate_session_loop` caches `session_name` and does not update it after a migration occurs inside `orchestrator.resume()`. The fix must propagate the new session name back to the loop so the next iteration uses the correct session.

## Scenarios

> As a user running a session that reaches turn 99, I want the continuation session to be processed exactly once so that no work is duplicated or overwritten on subsequent turns.

```gherkin
Feature: Centennial Turn Switch Session Name Propagation

  Scenario: Continuation session is processed only once
    Given a session "my-session" with turns 01-99 all completed
    When I start a resume loop on "my-session"
    Then the first iteration triggers a centennial migration to "my-session-2"
    And the second iteration resumes "my-session-2" (not "my-session")
    And the second iteration sees PENDING_PLAN for "my-session-2/01"
    And no further migration occurs

  Scenario: Normal turn progression without migration
    Given a session "my-session" with turns 01-05 completed
    When I start a resume loop on "my-session"
    Then the loop progresses through turns 06, 07, ...
    And the session name does NOT change
    And each turn is processed exactly once
```

## Edge Cases

- **Session Name Consistency**: If the migration creates a continuation name that collides with an existing session (e.g., user manually created `my-session-2`), the migration will overwrite turn 01. The fix does not address this rare race condition; the existing behavior is to overwrite.
- **Multiple Migrations in a Single Loop**: If a session somehow continues past turn 99 of a continuation session (e.g., turn 99 of `my-session-2`), the same migration logic applies. The fix's session name update mechanism must handle any number of migrations across iterations.
- **Cancelled Plan During Migration Turn**: If the user cancels the plan during the migration turn's execution, the `trigger_new_plan` returns `"CANCELLED"` and `_handle_planning_and_execution` returns None. In this case, the loop should break (current behavior is correct). The session name update should only occur when a migration actually happened and a plan was executed.

## Deliverables

- [ ] **Contract** - Modify `IRunPlanUseCase.resume()` return type from `Optional[ExecutionReport]` to `tuple[str, Optional[ExecutionReport]]` where the first element is the actual session name used (may differ from input after migration).
- [ ] **Logic** - Update `SessionLifecycleManager.resume()` to return `(new_session_name, report)` instead of just `report`. Propagate the session name from `_handle_planning_and_execution()`.
- [ ] **Logic** - Update `SessionOrchestrator.resume()` to return the updated session name from the lifecycle manager.
- [ ] **Logic** - Update `_orchestrate_session_loop` in `session_cli_handlers.py` to unpack the new return value and assign `session_name = actual_session_name` after each `orchestrator.resume()` call.
- [ ] **Migration** - Update all tests that mock `orchestrator.resume()` to return the tuple `(session_name, ExecutionReport)` instead of just the report.
- [ ] **Logic** - Add a regression test in `tests/suites/integration/core/services/test_session_orchestration_integration.py` that exercises the full resume loop across the centennial boundary and verifies no redundant migration.
- [ ] **Refactor** - Remove the now-unnecessary `current_name` variable reassignment pattern from the loop and ensure all guard conditions (loop_guard) still function correctly.

## Implementation Notes

Filled by the Developer during implementation.

## Implementation Plan

The fix consists of two changes:
1. **Contract Change**: `IRunPlanUseCase.resume()` returns a tuple `(actual_session_name: str, report: Optional[ExecutionReport])`. This is a breaking change for test mocks.
2. **Loop Update**: `_orchestrate_session_loop` unpacks the tuple and updates `session_name` on each iteration.

An alternative approach (not requiring contract change) is to check after each resume whether the session's latest turn is still "99" and if so, resolve the continuation via `session_manager.get_latest_session_name()`. However, this is less explicit and duplicates logic. The contract change is cleaner and aligns with Dependency Injection principles.
