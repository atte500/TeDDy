# Vertical Slice 09: Enhance `edit` Action Safety

### 1. Business Goal

To improve the safety and predictability of the `edit` action by preventing ambiguous modifications. If a user provides a `find` string that matches multiple times within a file, the action should fail instead of silently modifying only one occurrence. This ensures that the AI's intent is unambiguous and prevents accidental, partial changes to a file.

### 2. Acceptance Criteria (Scenarios)

*   **Scenario 1: `edit` fails when `find` string has multiple occurrences**
    *   **Given:** A file `test.txt` contains the content "hello world, hello again".
    *   **When:** An `edit` action is executed with `find: "hello"` and `replace: "goodbye"`.
    *   **Then:** The action should fail with a `FAILURE` status.
    *   **And:** The file `test.txt` must remain unchanged.
    *   **And:** The execution report's `error` field should state that multiple occurrences were found.
    *   **And:** The execution report's `output` field should contain the original file content "hello world, hello again".

*   **Scenario 2: `edit` succeeds when `find` string has exactly one occurrence**
    *   **Given:** A file `test.txt` contains the content "hello world".
    *   **When:** An `edit` action is executed with `find: "hello"` and `replace: "goodbye"`.
    *   **Then:** The action should succeed with a `COMPLETED` status.
    *   **And:** The file `test.txt` should be updated to "goodbye world".

*   **Scenario 3: `edit` fails when `find` string has zero occurrences**
    *   **Given:** A file `test.txt` contains the content "hello world".
    *   **When:** An `edit` action is executed with `find: "goodbye"`.
    *   **Then:** The action should fail with a `FAILURE` status (preserving existing behavior).
    *   **And:** The file `test.txt` must remain unchanged.
    *   **And:** The error report should indicate the text was not found.

### 3. Interaction Sequence

1.  The `PlanService` receives an `EditAction`.
2.  It calls the `edit_file` method on the `FileSystemManager` outbound port.
3.  The `LocalFileSystemAdapter` implements the `edit_file` method:
    a. It reads the entire content of the target file.
    b. It uses a string counting method (e.g., `content.count(find)`) to check the number of occurrences of the `find` string.
    c. **If the count is > 1:** It raises a new domain-specific exception, `MultipleMatchesFoundError`, attaching the original file content to the exception.
    d. **If the count is 0:** It raises the existing `SearchTextNotFoundError` (as before).
    e. **If the count is 1:** It performs the replacement and writes the content back to the file.
4.  The `PlanService` has a new `except MultipleMatchesFoundError as e:` block.
5.  Inside this block, it creates a `FAILURE` `ActionResult`, populating the `error` message and setting the `output` to the original file content from the exception (`e.content`).
6.  The `ActionResult` is added to the `ExecutionReport`.

### 4. Scope of Work (Components)

-   [ ] **Hexagonal Core:** Update `domain_model.md` to include a new `MultipleMatchesFoundError` domain exception.
-   [ ] **Hexagonal Core:** Update `ports/outbound/file_system_manager.md` to specify that `edit_file` must raise `MultipleMatchesFoundError`.
-   [ ] **Hexagonal Core:** Update `services/plan_service.md` to document the new `try/except` block for handling `MultipleMatchesFoundError`.
-   [ ] **Adapter:** Update `adapters/outbound/file_system_adapter.md` to document the new implementation logic for counting occurrences.
