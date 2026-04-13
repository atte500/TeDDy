# Bug: TUI Regression Test Failure (status item missing)

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config.md](../milestones/10-interactive-session-and-config.md)

## Symptoms
The test `test_regression_execution_log_removed` fails in Windows CI.
It asserts that a `DetailItem` with key `status` exists in the `ParameterDetail` pane after execution, but it is not found.

### Actual Output
```
>           assert any(item.data.get("key") == "status" for item in detail_items)
E           assert False
```

## System Model

### Understanding
The TUI (`ReviewerApp`) uses a `ParameterDetail` pane to show details of the selected action. When an action has been executed, it should show its execution status and other relevant parameters. `DetailItem` widgets are used to display these key-value pairs.

### Discrepancies
- The `status` key is expected in the `DetailItem` list but is missing during the test execution on Windows.

## Solution

### Implemented Fixes
- **Logic Guard:** Added a race-condition guard to `_update_detail_view` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`. The guard prevents background metadata updates (`RATIONALE_ROOT`) from overwriting the detail view if the user or a test has already moved the cursor to another node.
- **Test Alignment:** Refactored `test_regression_execution_log_removed` to be more robust by:
    1. Moving the tree cursor to the target node.
    2. Directly invoking the update logic.
    3. Providing multiple pauses for the `ListView` DOM to settle.

### Prevention
- Use explicit logic guards in TUI update handlers that are called asynchronously (e.g., via `call_after_refresh`) to ensure they don't overwrite more recent, intentional state changes.
- In TUI unit tests, provide sufficient `pilot.pause()` cycles for asynchronous widget updates (like `ListView.append`) to be reflected in the DOM before making assertions.
