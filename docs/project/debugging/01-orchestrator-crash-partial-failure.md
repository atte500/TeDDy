# Bug: Orchestrator Crash on Partial Execution Failure

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

### Expected Behavior
When a multi-action plan is executed, if one action fails (e.g., an `EDIT` action following an `EXECUTE` action), the orchestrator should catch the failure, halt further execution (unless `allow_failure` is set), and produce a valid `ExecutionReport`.

### Actual Behavior
The program crashes during execution when an `EDIT` action fails after state has been modified by a previous action.

### Reproduction Steps
1. Create a plan with two actions:
   - `EXECUTE` (modifies a file or performs some state change).
   - `EDIT` (attempts to modify a file in a way that fails, e.g., missing file or mismatching blocks).
2. Run `teddy execute` on the plan.
3. Observe crash instead of report.

## Context & Scope

### Regressing Delta
TBD - Investigation required.

### Environmental Triggers
Multi-action plans involving state modification followed by a failing file operation.

### Ruled Out
- `ActionDispatcher.dispatch_and_execute` internal execution (wrapped in try/except).

## Diagnostic Analysis

### Causal Model
The `ExecutionOrchestrator` runs an execution loop (`_process_plan_actions`). For each action, it calls `_handle_action_in_loop` -> `_dispatch_single_action` -> `ActionExecutor.confirm_and_dispatch`.

`ActionExecutor.confirm_and_dispatch` attempts to create a `ChangeSet` (for diffing) *before* the action is dispatched to the `ActionDispatcher`. If this is an `EDIT` action, `ActionChangeSetBuilder` uses `EditSimulator` to simulate the change against the current file on disk.

If the simulation fails (e.g., `SearchTextNotFoundError` due to a mismatch caused by a previous action in the same plan), the exception bubbles up through `ActionExecutor` and `ExecutionOrchestrator` without being caught, as `ExecutionOrchestrator` only expects exceptions to be handled within `ActionDispatcher.dispatch_and_execute`.

### Discrepancies
- Orchestrator should catch all execution-related exceptions. Conflict: Crash reported during mid-execution failure. (resolved: Unhandled exception in `ActionExecutor.confirm_and_dispatch` pre-dispatch logic).

### Investigation History
1. Hypothesis: Crash occurs in pre-dispatch logic of `ActionExecutor.confirm_and_dispatch` (e.g. `create_change_set`).
2. Observation: MRE crash stack trace points to `SearchTextNotFoundError` inside `ActionExecutor.confirm_and_dispatch`.
3. Conclusion: The orchestrator's execution loop lacks a high-level guard for runtime failures occurring during action preparation/confirmation.

## Solution

### Implemented Fixes
- Added `handle_failed_action` to `ActionExecutor` to allow creation of failure logs for errors occurring outside the dispatcher.
- Wrapped the action dispatch logic in `ExecutionOrchestrator._handle_action_in_loop` in a `try/except` block to catch runtime exceptions during action preparation (e.g., `EditSimulator` failures).

### Prevention
- A new regression test will be added to `tests/suites/acceptance/test_execute_mid_plan_failure.py` that specifically executes a plan where a state change causes a subsequent action to fail, ensuring it produces a report instead of crashing.
