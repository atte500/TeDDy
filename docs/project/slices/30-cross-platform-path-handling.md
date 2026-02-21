# Slice 30: Implement Centralized Path Normalization

## 1. Business Goal

To ensure the `teddy` executor functions reliably on all major operating systems by making file-based actions (`CREATE`, `EDIT`, `READ`, `PRUNE`) robust to variations in path separator characters (`/` vs. `\`). This will fix a critical bug preventing successful plan execution on Windows.

This work is based on the problem defined in our discovery session and is validated by the successful technical spike which proved the "Centralized Normalization" approach is correct.

## 2. Architectural Changes

The sole architectural change will be within the **`MarkdownPlanParser` service** (`src/teddy_executor/core/services/markdown_plan_parser.py`). This service will now be responsible for sanitizing all file path inputs at the boundary of the system, ensuring that all downstream components operate on clean, consistent, POSIX-style paths.

A new private helper method, `_normalize_path`, will be introduced and integrated into the existing parsing logic to handle this transformation.

## 3. Scope of Work

-   [x] **Implement Normalization Utility:**
    -   In `src/teddy_executor/core/services/markdown_plan_parser.py`, create a new private helper method `_normalize_path(self, path: str) -> str`.
    -   This method must replace all occurrences of `\` with `/`.

-   [x] **Integrate into Parsing Logic:**
    -   Modify the `_parse_action_metadata` method to call `_normalize_path` on the file path value extracted from `link_node.target` or as raw text.
    -   Modify the `_parse_message_and_optional_resources` method to call `_normalize_path` on all file paths extracted for `Handoff Resources`.

-   [x] **Add Unit Tests:**
    -   In a new or existing test file for the `MarkdownPlanParser`, add specific test cases that assert:
        -   A plan with a Windows-style path (e.g., `path\to\file.txt`) results in an `ActionData` object with a normalized path (`path/to/file.txt`).
        -   A plan with a mixed-style path (e.g., `path/to\file.txt`) is also correctly normalized.

-   [x] **Add Acceptance Test:**
    -   Create a new acceptance test file (e.g., `tests/acceptance/test_cross_platform_paths.py`).
    -   This test must perform the following:
        1.  Create a temporary file on disk.
        2.  Construct a plan string for an `EDIT` action that references this file using **backslashes (`\`)**.
        3.  Execute the plan using `teddy execute --plan-content`.
        4.  Assert that the execution report shows `SUCCESS` and that no validation errors occurred.

## 4. Acceptance Criteria

### Scenario: Executing a plan with Windows-style paths
-   **Given** a file named "pyproject.toml" exists with the content "Hello".
-   **And** a plan is created for an `EDIT` action with the file path "pyproject.toml" specified using backslashes (e.g., if in a dir, `.\pyproject.toml`).
-   **And** the `FIND` block in the plan is "Hello".
-   **When** the user executes the plan via the `teddy` CLI.
-   **Then** the plan should execute successfully.
-   **And** the execution report's "Overall Status" should be `SUCCESS`.
