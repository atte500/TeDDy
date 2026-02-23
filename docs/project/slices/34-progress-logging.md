# Slice 34: Execution Progress Logging

## 1. Business Goal
To improve the user experience during plan execution by providing real-time feedback. This will be achieved by printing log messages to the console indicating the start and completion status of each action.

## 2. Architectural Changes
This feature will leverage the existing standard Python `logging` module already configured in the project. The core logic will be added to the `ActionDispatcher` service, which is the central point for all action execution.

## 3. Scope of Work

All changes will be made in `src/teddy_executor/core/services/action_dispatcher.py`.

-   [x] **Import `logging`:** Add `import logging` to the file.
-   [x] **Initialize Logger:** Get a module-level logger instance with `logger = logging.getLogger(__name__)`.
-   [x] **Add "Executing" Log:** In the `dispatch_and_execute` method, before an action is executed, add an `INFO` level log message (e.g., `logger.info(f"Executing: {log_summary}")`).
-   [x] **Add "Success" Log:** After an action successfully executes, add an `INFO` level log message (e.g., `logger.info(f"Success: {log_summary}")`).
-   [x] **Add "Failure" Log:** If an action fails (either through a caught exception or a non-zero return code), add an `INFO` level log message (e.g., `logger.info(f"Failure: {log_summary}")`).

## Implementation Summary

- **Feature Delivered:** Real-time console progress logging during plan execution.
- **Core Implementation:** Added standard Python `logging` to `ActionDispatcher.dispatch_and_execute` to emit `INFO` level logs for the `Executing`, `Success`, and `Failed` states of each action.
- **User Feedback Iteration:** Following the initial implementation, the user requested a specific format (`Executing Action: [TYPE] - [Description]`) and the removal of the standard `INFO:logger_name:` prefix.
- **Formatting Fix:** `ActionDispatcher` was updated to construct the string `f"{action.type.upper()} - {action.description}"` for the log message.
- **Prefix Removal:** The entry point `main.py` was updated to call `logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stderr)], force=True)`. The `force=True` argument was strictly required to override default handlers injected by third-party libraries (like Typer), ensuring the logs appear cleanly as requested.
- **Acceptance Testing:** The `test_progress_logging.py` test uses the `capsys` fixture to capture `stderr` (which bypasses Typer's `CliRunner` stdout capture when writing directly to `sys.stderr`) to assert the exact formatting of the logs.

## 4. Acceptance Criteria

### Scenario 1: Successful Action Execution
-   **Given** a plan that contains a simple, successful action (e.g., `read` on an existing file).
-   **When** `teddy execute` is run on the plan.
-   **Then** the console output should show an "Executing: READ..." message.
-   **And** the console output should subsequently show a "Success: READ..." message.

### Scenario 2: Failed Action Execution
-   **Given** a plan that contains a simple, failing action (e.g., `read` on a non-existent file).
-   **When** `teddy execute` is run on the plan.
-   **Then** the console output should show an "Executing: READ..." message.
-   **And** the console output should subsequently show a "Failure: READ..." message.
