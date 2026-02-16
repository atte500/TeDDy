# Specification: Concise Report Format

## 1. Overview

This document specifies the format for the **Concise Report**, which is the primary output of the `teddy execute` command in the manual, CLI-driven workflow. It is optimized for a chat-based, copy-paste workflow.

## 2. Guiding Principles

-   **Clarity over Verbosity:** The report should be easy to scan, omitting unnecessary details from the original plan.
-   **Minimize Deviation:** The format should align closely with the existing implementation to simplify refactoring.
-   **Markdown Native:** `params` and `details` fields must be rendered as clean, readable Markdown (e.g., nested lists), not as raw JSON dumps.
-   **Action-Oriented Feedback:** For failures, the report must provide clear, actionable hints.
-   **Robust Formatting:** The report must use smart code block fencing to prevent rendering issues.

## 3. Report Structure

The report is composed of a header, followed by the `Execution Summary`, and then a conditional section for resource contents. All action details, both for success and failure, are included directly within the `Execution Summary`.

1.  **Report Header:** High-level summary (Overall Status, Timestamps).
2.  **Execution Summary:** The single source of truth for the action-by-action log.
3.  **Resource Contents (Conditional):** Appears if `READ` actions succeeded, or if `CREATE` or `EDIT` actions failed, to provide necessary context.

## 4. Core Formatting Requirements

1.  **Action Header Format:** Action headers in the log should follow the format: `#### ACTION_TYPE: [Description or Target]`.
    -   Example for `EDIT`: `#### EDIT: src/main.py`
    -   Example for `EXECUTE`: `#### EXECUTE: "Run unit tests"`
2.  **Status Formatting:** Status should be rendered on its own line, using the raw, uppercase status value from the system. Valid values are `SUCCESS`, `FAILURE`, `VALIDATION_FAILED`, and `SKIPPED`.
    ```markdown
    - **Status:**
      - SUCCESS
    ```
3.  **Params Formatting:** If an action has parameters, they should be rendered as a nested Markdown list, not a JSON string.
    ```markdown
    - **Params:**
      - **File Path:** docs/spec.md
      - **Description:** A new spec.
    ```
4.  **No Backticks on Resource Paths:** Resource paths in headers or links should be clean text or Markdown links.
5.  **Smart Fencing:** Code blocks must use nesting-aware fencing.
6.  **Language-Aware Code Blocks:** Fenced code blocks displaying file contents must use the correct language identifier based on the file's extension (e.g., ` ```python`), not defaulting to `text`.

## 5. Content Requirements

### 5.1. General
-   **Omit Redundant Content:** The report **must not** include the verbatim content of `CREATE` or `EDIT` (`FIND`/`REPLACE`) blocks from the plan.

### 5.2. `EXECUTE` Action Log
-   **Show Expected Outcome:** The log for an `EXECUTE` action must include the `Expected Outcome` from the original plan.

### 5.3. Failure Handling & Hints
All failure details are rendered inline within the `Execution Summary` for the specific action that failed.

-   **Specify Failed `FIND` Block:** For an `EDIT` failure, the error must specify *which exact* `FIND` block failed.
-   **Provide Actionable Hint:** For a `FIND` mismatch, include the hint: *"Hint: Try to provide more context...including whitespace and indentations."*
-   **Check for Pre-existing Changes:** Before reporting a `FIND` mismatch, check if the `REPLACE` content is already present. If so, note that the change may have already been applied.
-   **Include Content on Failure:** If a `CREATE` or `EDIT` action fails, the full content of the target file must be displayed in the `Resource Contents` section to provide context for correction.

## 6. Example Structure

``````markdown
# Execution Report: Refactor Core Services
- **Overall Status:** FAILURE
- **Start Time:** 2023-10-28T12:00:00Z
- **End Time:** 2023-10-28T12:00:03Z

## Execution Summary

### Action Log

#### `CREATE`: src/teddy_executor/core/services/new_service.py
- **Status:**
  - SUCCESS

#### `EDIT`: src/teddy_executor/core/services/action_factory.py
- **Status:**
  - FAILURE
- **Error:** The `FIND` block did not match. The change may have already been applied.
  - **FIND Block Content:**
    ````python
    # Old logic to be replaced
    return legacy_logic()
    ````
  - **Hint:** Try to provide more context in the FIND block and match the content exactly, including whitespace and indentations.

#### `EXECUTE`: "Run unit tests for the action factory"
- **Status:**
  - SUCCESS
- **Expected Outcome:** All tests for the action factory should pass.
- **Execution Details:**
  - **Return Code:** `0`
  #### `stdout`
  ````text
  PASSED tests/unit/core/services/test_action_factory.py::test_creation
  ````
``````
