# Slice 34: Execution Progress Logging

## 1. Business Goal
To improve the user experience during plan execution by providing real-time feedback. This will be achieved by printing log messages to the console indicating the start and completion status of each action.

## 2. Architectural Changes
This feature will leverage the existing standard Python `logging` module already configured in the project. The core logic will be added to the `ActionDispatcher` service, which is the central point for all action execution.

## 3. Scope of Work

All changes will be made in `src/teddy_executor/core/services/action_dispatcher.py`.

-   [ ] **Import `logging`:** Add `import logging` to the file.
-   [ ] **Initialize Logger:** Get a module-level logger instance with `logger = logging.getLogger(__name__)`.
-   [ ] **Add "Executing" Log:** In the `dispatch_and_execute` method, before an action is executed, add an `INFO` level log message (e.g., `logger.info(f"Executing: {log_summary}")`).
-   [ ] **Add "Success" Log:** After an action successfully executes, add an `INFO` level log message (e.g., `logger.info(f"Success: {log_summary}")`).
-   [ ] **Add "Failure" Log:** If an action fails (either through a caught exception or a non-zero return code), add an `INFO` level log message (e.g., `logger.info(f"Failure: {log_summary}")`).

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
