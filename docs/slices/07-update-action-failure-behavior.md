# Vertical Slice 07: Update Action Failure Behavior

### 1. Business Goal

To make the tool's feedback more robust by providing more context on failure. When the `create_file` or `edit` actions fail due to a precondition not being met, the system should not just report failure but also return the current state of the file in question. This gives the AI agent immediate, actionable information to correct its next plan.

### 2. Acceptance Criteria (Scenarios)

**Scenario 1: `create_file` action on an existing file**
- **Given** a file named `existing_file.txt` with content "original content".
- **When** the `teddy` executor is run with a plan to `create_file` at `existing_file.txt`.
- **Then** the execution report for that action should show a `status` of `FAILED`.
- **And** the report's `output` should contain the text "original content".
- **And** the file `existing_file.txt` should remain unchanged.

**Scenario 2: `edit` action with `find_block` not found**
- **Given** a file named `target_file.txt` with content "some initial text".
- **When** the `teddy` executor is run with a plan to `edit` the file `target_file.txt` with a `find_block` of "non-existent text".
- **Then** the execution report for that action should show a `status` of `FAILED`.
- **And** the report's `output` should contain the text "some initial text".
- **And** the file `target_file.txt` should remain unchanged.

### 3. Interaction Sequence

1.  The `PlanService` receives a `CreateFileAction` or `EditFileAction`.
2.  It calls the corresponding method (`create_file` or `edit_file`) on the `FileSystemManager` outbound port.
3.  The `LocalFileSystemAdapter`, which implements the port, detects the precondition failure (file already exists or `find_block` is not found).
4.  The adapter raises a specific, custom exception (e.g., `FileAlreadyExistsError` or `TextBlockNotFoundError`) that includes the path to the relevant file.
5.  The `PlanService` catches this specific exception.
6.  Inside the `except` block, the `PlanService` calls the `read_file` method on the `FileSystemManager` port, passing the file path from the exception.
7.  The `PlanService` creates an `ActionResult` with `status='FAILED'` and sets the `output` to the content returned by `read_file`.
8.  This result is appended to the final execution report.

### 4. Scope of Work (Components)

-   [ ] Hexagonal Core: `Domain Model` (Update descriptions in `domain_model.md`)
-   [ ] Hexagonal Core: `PlanService` (Update `plan_service.md` to document new exception handling)
-   [ ] Hexagonal Core: `FileSystemManager` (Update `file_system_manager.md` to document new exceptions in its contract)
-   [ ] Adapter: `LocalFileSystemAdapter` (Update `file_system_adapter.md` to document the implementation of the new exception-throwing logic)
