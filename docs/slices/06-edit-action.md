# Vertical Slice 06: Implement `edit` Action

## 1. Business Goal

To extend the executor's capabilities by allowing it to perform in-place modifications of files. This enables plans to not only create and read files but also to alter existing ones, which is critical for configuration management, code generation, and automated refactoring tasks.

## 2. Acceptance Criteria (Scenarios)

### Scenario: Successfully editing a file

-   **Given** a file exists at `path/to/file.txt` with the content "Hello world!".
-   **When** a plan is executed with an `edit` action to replace "world" with "TeDDy" in that file.
-   **Then** the execution report should indicate success.
-   **And** the file at `path/to/file.txt` should now contain "Hello TeDDy!".

### Scenario: Attempting to edit a non-existent file

-   **Given** no file exists at `nonexistent/file.txt`.
-   **When** a plan is executed with an `edit` action targeting that file.
-   **Then** the execution report should indicate failure.
-   **And** the error message should clearly state that the file was not found.

### Scenario: Attempting to edit a file where the search text is not found

-   **Given** a file exists at `path/to/file.txt` with the content "Hello world!".
-   **When** a plan is executed with an `edit` action to replace "goodbye" with "farewell" in that file.
-   **Then** the execution report should indicate failure.
-   **And** the error message should clearly state that the search text was not found.
-   **And** the output of the action log should be the full, unmodified content of the file, "Hello world!".

## 3. Interaction Sequence

1.  The `CliInboundAdapter` receives a plan string containing an `edit` action.
2.  It invokes the `PlanService` via the `RunPlanUseCase` inbound port.
3.  The `PlanService` parses the plan string into a list of action dictionaries.
4.  For the `edit` action dictionary, it calls the `ActionFactory`.
5.  The `ActionFactory` validates the parameters and creates an `EditAction` domain object.
6.  The `PlanService` receives the `EditAction` object and dispatches it to its internal `_execute_single_action` method.
7.  The method identifies the action as an `EditAction` and calls the `edit_file` method on the `FileSystemManager` outbound port, passing the `file_path`, `find`, and `replace` parameters.
8.  The `LocalFileSystemAdapter`, which implements the `FileSystemManager` port, executes the logic:
    a. It reads the content of the file at `file_path`.
    b. If the `find` string is not present in the content, it immediately returns a failure result. This result **must** include an appropriate error message and the full, unmodified file content as the output.
    c. If the `find` string is present, it performs a string replacement.
    d. It writes the modified content back to the same file.
9.  The `LocalFileSystemAdapter` returns a success or failure result.
10. The `PlanService` records the result in the `ExecutionReport` and returns it.

## 4. Scope of Work (Components)

-   [ ] **Hexagonal Core:** Update `domain_model.md` to include the `EditAction` model.
-   [ ] **Hexagonal Core:** Update `services/plan_service.md` to handle the `EditAction`.
-   [ ] **Hexagonal Core:** Update `factories/action_factory.md` to create the `EditAction`.
-   [ ] **Hexagonal Core:** Update `ports/outbound/file_system_manager.md` with an `edit_file` method.
-   [ ] **Adapter:** Update `adapters/outbound/file_system_adapter.md` to implement the `edit_file` method.
