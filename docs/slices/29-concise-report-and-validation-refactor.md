# Concise Report and Validation Refactor

## 1. Business Goal

To improve the clarity, correctness, and robustness of the `teddy execute` workflow. This will be achieved by refactoring the concise report format to align with the canonical specification and by enhancing the plan validation system to catch common errors before execution.

-   **Report Specification:** [docs/specs/concise-report-format.md](/docs/specs/concise-report-format.md)
-   **Validation Specification:** [docs/specs/plan-format-validation.md](/docs/specs/plan-format-validation.md)

## 2. Architectural Changes

-   **`src/teddy_executor/core/services/templates/concise_report.md.j2` (MODIFY):** This template will be completely replaced to implement the new formatting rules.
-   **`src/teddy_executor/core/services/markdown_report_formatter.py` (MODIFY):** The context preparation logic will be updated to remove JSON serialization of `params`.
-   **`src/teddy_executor/core/services/plan_validator.py` (MODIFY):** The `_validate_edit_action` method will be extended with a new validation rule.
-   **`src/teddy_executor/core/services/markdown_plan_parser.py` (MODIFY):** The parsing logic will be enhanced to detect structural and semantic plan errors.
-   **`tests/acceptance/test_markdown_reports.py` (MODIFY):** Acceptance tests will be refactored to assert against the new report format.
-   **`tests/unit/core/services/test_plan_validator.py` (MODIFY):** A new unit test will be added for the new validation rule.
-   **`tests/unit/core/services/test_markdown_plan_parser.py` (MODIFY/CREATE):** New unit tests will be added for the new parsing validation rules.

## 3. Scope of Work

### Feature 1: Report Formatting Refactor

-   [ ] **Update Jinja2 Template (`.../concise_report.md.j2`):**
    -   [ ] Replace the entire file with a new template that precisely follows the specification.
    -   [ ] Ensure the `Execution Summary` is the first major section after the header.
    -   [ ] Ensure an action's `Status` is rendered on a new, indented line.
    -   [ ] Remove all unnecessary horizontal lines (`---`).
    -   [ ] Ensure all code blocks (`stdout`, `stderr`, resource content) are rendered without any indentation.
    -   [ ] Implement logic to display `Failed Action Details` only when actions have failed, including file content for `EDIT`/`CREATE` failures.
    -   [ ] Implement logic to display `Resource Contents` only when `READ` actions have succeeded.
-   [ ] **Update Formatter Service (`.../markdown_report_formatter.py`):**
    -   [ ] Remove the `to_json` filter. The template must be responsible for rendering `params` as a clean Markdown list.
-   [ ] **Update Execution Logic (e.g., `ExecutionOrchestrator`):**
    -   [ ] When an `EDIT` action's `FIND` block mismatch occurs, before reporting the error, check if the `REPLACE` block's content already exists in the file. If so, augment the error message to note that the change may have already been applied.
-   [ ] **Update Acceptance Tests (`.../test_markdown_reports.py`):**
    -   [ ] Refactor existing tests to validate the new, precise report structure and content.

### Feature 2: Validation Logic Enhancements

-   [ ] **Implement Parser Structural Checks (`.../markdown_plan_parser.py`):**
    -   [ ] In the `_parse_actions` method, modify the loop to check if an action's type is unknown. If it is, raise an `InvalidPlanError`.
    -   [ ] Enhance the parsing logic to detect and raise an `InvalidPlanError` for plans with unexpected free-form text between valid action blocks.
-   [ ] **Implement Validator Logic Checks (`.../plan_validator.py`):**
    -   [ ] In `_validate_create_action`, add a check to ensure the target file does not already exist.
    -   [ ] In `_validate_edit_action`, upgrade the `FIND` block check to ensure the content appears **exactly once** (not zero or multiple times).
    -   [ ] In `_validate_edit_action`, add a check to ensure the `find` and `replace` block contents are not identical.
-   [ ] **Add Unit Tests for Validation:**
    -   [ ] In `.../test_plan_validator.py`, add new test cases for the three new validation rules (`CREATE` file exists, `EDIT` `FIND` is not unique, and `EDIT` `find`/`replace` are identical).
    -   [ ] In the appropriate test file (e.g., `test_markdown_plan_parser.py`), add new test cases that assert `InvalidPlanError` is raised for plans containing unknown actions or malformed structures.

## 4. Acceptance Criteria

### Report Formatting
-   **Given** a plan that executes successfully, **when** `teddy execute` is run, **then** the report's `Execution Summary` should appear immediately after the header, with each action's `Status` on a new line.
-   **Given** a plan with a failed `EDIT` action, **when** `teddy execute` is run, **then** the report must contain a `Failed Action Details` section showing the error, hints, and the full, non-indented content of the target file.
-   **Given** a plan with a failed `EXECUTE` action, **when** `teddy execute` is run, **then** the `stdout` and `stderr` must be displayed in separate, non-indented code blocks.

### Validation Logic
-   **Given** a plan containing an action type of `UNKNOWN_ACTION`, **when** `teddy execute` is run, **then** the command must fail with a validation error stating the action is unknown.
-   **Given** a plan with free-form text between two valid action blocks, **when** `teddy execute` is run, **then** the command must fail with a validation error about a malformed structure.
-   **Given** a plan with an `EDIT` action where the `FIND` and `REPLACE` blocks are identical, **when** `teddy execute` is run, **then** the command must fail with a validation error stating that the blocks are the same.
