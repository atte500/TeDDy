# Markdown Report Generator & Manual Workflow

## 1. Goal (The "Why")

The primary goal is to enable a robust, manual, non-interactive workflow for using TeDDy with external chat interfaces. This will be achieved by implementing a Markdown-based execution report generator to replace the current YAML output.

This work is a foundational prerequisite for the full interactive session workflow but provides immediate value by improving the tool's usability and observability.

This brief is based on the canonical specifications that define the new workflow and report formats:
- [Manual CLI Workflow Specification](../specs/manual-cli-workflow.md)
- [Report Format Specification](../specs/report-format.md)

## 2. Proposed Solution (The "What")

We will introduce a new, dedicated service for formatting reports and integrate a mandatory pre-flight validation step into the execution lifecycle.

1.  **Pre-flight Validation:** Before any plan execution, a validation step will be run to check for common errors (e.g., malformed plan, `FIND` block mismatches). If validation fails, execution will terminate immediately, and a specific validation failure report will be generated.

2.  **`MarkdownReportFormatter` Service:** A new service, `MarkdownReportFormatter`, will be created (behind an `IMarkdownReportFormatter` port).
    -   **Responsibility:** To convert the `ExecutionReport` domain object into a Markdown string.
    -   **Compliance:** The output must strictly adhere to the `report-format.md` spec.
    -   **Manual Workflow Features:** It must implement the special formatting rules from the `manual-cli-workflow.md` spec, including:
        -   A `## Resource Contents` section for successful `READ` actions.
        -   A `## Failed Action Details` section, including the actual content of relevant files.
        -   Graceful reporting of unsupported actions (`INVOKE`, `RETURN`).
        -   "Smart Fencing" for all code blocks to ensure robust parsing.

3.  **CLI Integration:** The `teddy execute` command in `main.py` will be refactored to:
    -   First, run the pre-flight validation.
    -   If validation passes, proceed with execution.
    -   After the existing action-by-action approval and execution loop is complete, use the new `MarkdownReportFormatter` service to generate the final report for `stdout` and the clipboard, completely replacing the legacy YAML output.

## 3. Implementation Analysis (The "How")

This work is a combination of new component creation and refactoring the existing command execution logic.

-   **New Components:** The `IMarkdownReportFormatter` port and its `MarkdownReportFormatter` implementation will be created.
-   **Core Logic Modifications:** The primary impact is within the `execute` command handler in `main.py`. This is where the pre-flight validation logic will be added, and where the call to the new formatting service will replace the old reporting mechanism.
-   **Dependency Injection:** The new service will be wired up in the composition root (`main.py`) using `punq`.
-   **Data Gathering:** Logic will need to be added to the `ExecutionOrchestrator` or the `execute` command handler to gather the necessary data for the enhanced manual workflow reports (e.g., reading file contents on failure).

## 4. Vertical Slices

This brief will be implemented in two distinct vertical slices.

---
### **Slice 1: Implement Pre-flight Validation & Core Formatter**
**Goal:** Replace the YAML report with a basic Markdown report and introduce the critical pre-flight validation gate.

-   [ ] Task: Implement Plan Validator:
    -   Create a `PlanValidator` service responsible for executing all pre-flight checks as defined in the specifications.
    -   Integrate this validator at the beginning of the `execute` command.
-   [ ] Task: Implement Core `MarkdownReportFormatter`:**
    -   Define the `IMarkdownReportFormatter` port.
    -   Create the `MarkdownReportFormatter` service.
    -   Implement the logic to generate a valid Markdown report for a successful execution, adhering to the base `report-format.md` spec.
-   [ ] Task: Integrate Formatter:
    -   Refactor the `execute` command to use the new formatter for all outputs (successful execution or validation failure), replacing the YAML report.

---
### **Slice 2: Implement Manual Workflow Report Enhancements**
**Goal:** Enhance the Markdown report with the specific sections required for a smooth manual, copy-paste workflow.

-   [ ] Task: Enhance Data Gathering:
    -   Update the execution logic to capture the results of `READ` actions.
    -   Update the failure handling logic to read the contents of files when `CREATE` or `EDIT` actions fail.
-   [ ] Task: Enhance Formatter for Resource Contents:
    -   Update the `MarkdownReportFormatter` to add the `## Resource Contents` section to the report for successful `READ` actions.
-   [ ] Task: Enhance Formatter for Failures:
    -   Update the formatter to add the `## Failed Action Details` section, including the fetched file contents.
-   [ ] Task: Enhance Formatter for Unsupported Actions:
    -   Update the formatter to correctly report `INVOKE` and `RETURN` actions as "Not Supported" in manual mode.

---
### **Slice 3: Implement Centralized Path Normalization**
**Goal:** Ensure file-based actions are robust to path separator variations across operating systems.

-   [ ] **Task: Implement Normalization Utility:**
    -   In `src/teddy_executor/core/services/markdown_plan_parser.py`, create a private helper `_normalize_path` to replace `\` with `/`.
-   [ ] **Task: Integrate into Parsing Logic:**
    -   Modify `_parse_action_metadata` and `_parse_message_and_optional_resources` to use `_normalize_path`.
-   [ ] **Task: Add Unit & Acceptance Tests:**
    -   Add tests to assert that Windows-style and mixed-style paths are correctly normalized and executed.

---
### **Slice 4: Implement Auto-Skip on Execution Failure**
**Goal:** Make plan execution more robust by automatically skipping subsequent actions after a failure.

-   [ ] **Task: Refactor `ExecutionOrchestrator`:**
    -   In the `execute` method, add a `halt_execution` flag that is set on failure.
    -   If the flag is `True`, subsequent actions are logged as `SKIPPED`.
-   [ ] **Task: Add Acceptance Test:**
    -   Create a test with a failing action followed by a valid action and assert the second action is `SKIPPED`.

---
### **Slice 5: Implement Comprehensive EDIT Validation**
**Goal:** Improve validation by reporting all `FIND` block failures in an `EDIT` action at once and providing a diff for mismatches.

-   [ ] **Task: Report All Failures in a Single Action:**
    -   Refactor `PlanValidator` to collect and return all validation errors from `_validate_edit_action` instead of raising on the first one.
-   [ ] **Task: Enhance "Not Found" Errors with a Diff:**
    -   Implement a helper in `PlanValidator` to find the best match for a failed `FIND` block and include a `difflib` diff in the validation error message.

---
### **Slice 6: Implement Report Generation Enhancements**
**Goal:** Improve the clarity, robustness, and user experience of the execution report.

-   [ ] **Task: Refactor Template:**
    -   Rename `concise_report.md.j2` to `execution_report.md.j2` and update all references.
-   [ ] **Task: Enhance Jinja2 Template:**
    -   Add smart fencing to validation errors and make reports for `chat_with_user`, `invoke`, and `return` more compact.
-   [ ] **Task: Implement Dynamic Code-Block Language:**
    -   Create a `get_language_from_path` utility, register it as a Jinja2 filter, and use it in the template.

---
### **Slice 7: Implement Execution Progress Logging**
**Goal:** Improve user experience by providing real-time console feedback during plan execution.

-   [ ] **Task: Add Logging to `ActionDispatcher`:**
    -   In `dispatch_and_execute`, add `INFO` level logs for "Executing", "Success", and "Failure" of each action.
