# Slice: Centennial Turn Switch – Session Name Propagation

- **Status:** In Progress
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

- [x] **Contract** - Modify `IRunPlanUseCase.resume()` return type from `Optional[ExecutionReport]` to `tuple[str, Optional[ExecutionReport]]` where the first element is the actual session name used (may differ from input after migration).
- [x] **Logic** - Update `SessionLifecycleManager.resume() to return `(new_session_name, report)` instead of just `report`. Propagate the session name from `_handle_planning_and_execution()`.
- [x] **Logic** - Update `SessionOrchestrator.resume() to return the updated session name from the lifecycle manager.
- [x] **Logic** - Update `_orchestrate_session_loop` in `session_cli_handlers.py` to unpack the new return value and assign `session_name = actual_session_name` after each `orchestrator.resume()` call.
- [x] **Migration** - Update all tests that mock `orchestrator.resume()` to return the tuple `(session_name, ExecutionReport)` instead of just the report.
- [▶] **Logic** - Add a regression test in `tests/suites/integration/core/services/test_session_orchestration_integration.py` that exercises the full resume loop across the centennial boundary and verifies no redundant migration.
- [ ] **Refactor** - Remove the now-unnecessary `current_name` variable reassignment pattern from the loop and ensure all guard conditions (loop_guard) still function correctly.

## Implementation Notes

### Contract Deliverable
- **Change**: Modified `IRunPlanUseCase.resume()` return type annotation from `Optional[ExecutionReport]` to `tuple[str, Optional[ExecutionReport]]`.
- **Test**: Created `tests/suites/unit/ports/inbound/test_run_plan_use_case_contract.py` with contract test that introspects the `resume` method's `__annotations__` to verify the tuple shape and the wrapped `ExecutionReport` type.
- **Test Locale**: Using `__annotations__` directly (not `typing.get_type_hints`) to avoid forward-reference resolution failures caused by `ProjectContext` being a `TYPE_CHECKING`-only import.
- **Verified**: Full test suite passes (861 passed, 3 skipped) after the annotation-only change, confirming no runtime regressions.

### SessionLifecycleManager Logic Deliverable
- **Change**: Modified `SessionLifecycleManager.resume()` to return `tuple[str, Optional[ExecutionReport]]`. Each branch returns `(session_name, report)` or `(actual_session_name, report)` after centennial migration.
- **Change**: `_handle_planning_and_execution()` returns `(actual_name, report)` from `trigger_new_plan()`.
- **Test**: Added `test_resume_returns_tuple_with_session_name_and_report` to `test_session_lifecycle_manager.py`.
- **Integration Note**: 21 acceptance/integration tests currently fail downstream because the outer loop and test mocks have not been updated yet. These failures will be resolved by loop update and migration deliverables.

### SessionOrchestrator Logic Deliverable
- **Change**: `SessionOrchestrator.resume()` already delegates to `self._lifecycle_manager.resume()` which now returns the tuple. No code change needed.

### Loop Update Deliverable
- **Change**: In `_orchestrate_session_loop`, changed `report = orchestrator.resume(...)` to `session_name, report = orchestrator.resume(...)`. This ensures `session_name` is updated after a centennial migration, preventing re-processing of the old session's turn 99.
- **Integration Recovery**: Updated `test_session_replan_loop.py` and `test_session_start_resequencing.py` to return `("session_name", report)` from `orchestrator.resume()` mocks. Fixed syntax error (missing closing parenthesis) in `test_session_start_resequencing.py` line 47.
- **Verification**: Full test suite passed (862 passed, 3 skipped) after integration recovery.

### Migration Deliverable
- **Change**: Updated two test files that mock `orchestrator.resume()`: `test_session_replan_loop.py` (2 tests) and `test_session_start_resequencing.py` (2 tests). All mocks now return `("session_name", ...)` tuples.
- **Verified**: Full test suite passes confirming all mock signatures are compatible with the new tuple return type.
