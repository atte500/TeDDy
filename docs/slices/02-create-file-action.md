# Vertical Slice 02: Implement `create_file` Action

## 1. Business Goal

As a user, I want the `teddy` executor to be able to create new files with specified content, as defined in a YAML plan. This allows the AI to generate new code, configuration, or documentation files within the project.

## 2. Acceptance Criteria (Scenarios)

*   **Scenario 1: Successfully create a new file**
    *   **Given:** A directory `temp_dir` exists and is empty.
    *   **And:** A YAML plan to create a file:
        ```yaml
        - action: create_file
          params:
            file_path: "temp_dir/new_file.txt"
            content: "Hello, World!"
        ```
    *   **When:** The user executes the plan with `teddy`.
    *   **And:** The user approves the action.
    *   **Then:** The file `temp_dir/new_file.txt` should be created.
    *   **And:** The content of `temp_dir/new_file.txt` should be "Hello, World!".
    *   **And:** The execution report should indicate the action was `COMPLETED`.

*   **Scenario 2: Attempt to create a file that already exists**
    *   **Given:** A file named `temp_dir/existing_file.txt` already exists.
    *   **And:** A YAML plan to create the same file:
        ```yaml
        - action: create_file
          params:
            file_path: "temp_dir/existing_file.txt"
            content: "Some new content."
        ```
    *   **When:** The user executes the plan with `teddy`.
    *   **And:** The user approves the action.
    *   **Then:** The action should fail.
    *   **And:** The file `temp_dir/existing_file.txt` should remain unchanged.
    *   **And:** The execution report should indicate the action `FAILED` with a message like "File already exists".

## 3. Interaction Sequence

1.  The `CLI Adapter` receives the YAML plan string.
2.  The `CLI Adapter` calls the `RunPlanUseCase` (inbound port) on the `PlanService`.
3.  The `PlanService` parses the YAML into a `Plan` domain object containing an `Action` of type `create_file`.
4.  The `PlanService` iterates through the actions. For the `create_file` action, it prompts the user for approval via the `UserInteraction` port (already implemented).
5.  If approved, the `PlanService` calls the `create_file` method on the `FileSystemManager` (new outbound port), passing the file path and content.
6.  The `LocalFileSystemAdapter` (new outbound adapter) implements the `FileSystemManager` port. It uses Python's standard library to write the content to the specified file path. It includes a check to prevent overwriting an existing file.
7.  The `LocalFileSystemAdapter` returns success or failure to the `PlanService`.
8.  The `PlanService` records the result in the `ExecutionReport` and continues to the next action or finishes.

## 4. Scope of Work (Components)

*   **Domain Model (`docs/core/domain_model.md`):**
    *   [ ] Update `Action` value object to include `create_file` as a valid type.
    *   [ ] Add attributes for `file_path` and `content`.
*   **Application Service (`docs/core/services/plan_service.md`):**
    *   [ ] Add logic to handle the `create_file` action type.
    *   [ ] Add `FileSystemManager` to its dependencies.
*   **Outbound Port (`docs/core/ports/outbound/file_system_manager.md`):**
    *   [ ] **CREATE:** Define a new port for file system operations with a `create_file(path, content)` method.
*   **Outbound Adapter (`docs/adapters/outbound/file_system_adapter.md`):**
    *   [ ] **CREATE:** Implement the `FileSystemManager` port for the local file system.
