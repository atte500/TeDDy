# Slice 31: Implement Auto-Skip on Execution Failure

## 1. Business Goal

To make the plan execution process more robust and predictable. If any action fails during execution, all subsequent actions in the plan must be automatically skipped. This prevents cascading failures and provides a clearer, more actionable report to the user and the AI. This will be the new default behavior.

## 2. Architectural Changes

The architectural changes will be confined to the **`ExecutionOrchestrator` service** (`src/teddy_executor/core/services/execution_orchestrator.py`).

The `execute` method's main loop will be refactored to incorporate a state flag that tracks whether a failure has occurred. This ensures the change is isolated to the component responsible for orchestrating the plan's lifecycle.

## 3. Scope of Work

-   [ ] **Refactor `ExecutionOrchestrator`:**
    -   In the `execute` method of `src/teddy_executor/core/services/execution_orchestrator.py`:
        -   Initialize a new boolean flag `halt_execution = False` before the main `for action in plan.actions:` loop.
        -   Inside the loop, at the beginning of each iteration, add a condition to check if `halt_execution` is `True`.
            -   If it is `True`, bypass the interactive confirmation and action dispatch.
            -   Instead, directly create an `ActionLog` with a status of `ActionStatus.SKIPPED` and a detail message like "Skipped because a previous action failed."
            -   Append this log and `continue` to the next iteration.
        -   After an action is dispatched and executed (`if should_dispatch:` block), check the returned `action_log.status`.
        -   If the status is `ActionStatus.FAILURE`, set `halt_execution = True`.

-   [ ] **Add Acceptance Test:**
    -   Create a new acceptance test file (e.g., `tests/acceptance/test_execution_flow.py`) or add to an existing one.
    -   The test must perform the following:
        1.  Construct a plan with at least two `EXECUTE` actions. The first action must be designed to fail (e.g., `exit 1`), and the second should be a simple, valid command (e.g., `echo "hello"`).
        2.  Run the plan using `teddy execute --plan-content` in non-interactive (`-y`) mode.
        3.  Assert that the final execution report shows an `Overall Status` of `FAILURE`.
        4.  Assert that the report contains two `ActionLog` entries.
        5.  Assert that the first action log has a status of `FAILURE`.
        6.  Assert that the second action log has a status of `SKIPPED` and contains the correct reason in its details.

## 4. Acceptance Criteria

### Scenario: An `EXECUTE` action fails mid-plan
-   **Given** a plan containing two `EXECUTE` actions.
-   **And** the first `EXECUTE` action is a command that will fail (e.g., `ls non_existent_directory`).
-   **And** the second `EXECUTE` action is a valid command (e.g., `echo "should be skipped"`).
-   **When** the user executes the plan.
-   **Then** the execution report's "Overall Status" should be `FAILURE`.
-   **And** the report should show the first action as `FAILURE`.
-   **And** the report should show the second action as `SKIPPED` with the reason "Skipped because a previous action failed."
