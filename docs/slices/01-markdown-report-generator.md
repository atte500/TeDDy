# Slice 01: Markdown Report Generator

**Source Brief:** [07-markdown-report-generator.md](../briefs/07-markdown-report-generator.md)

## 1. Business Goal
To improve the usability and observability of the TeDDy manual workflow by replacing the current YAML execution report with a comprehensive, human-readable Markdown report. This includes introducing a pre-flight validation step to provide immediate feedback on common plan errors, preventing failed execution runs.

## 2. Interaction Sequence
1.  The user copies a Markdown plan to the clipboard.
2.  The user invokes the `teddy execute` command (with no arguments). The system reads the plan from the clipboard.
3.  The system performs a pre-flight validation on the plan.
4.  **Failure Path (Validation):** If validation fails, the system terminates immediately, prints a Markdown-formatted validation failure report to `stdout`, and copies it to the clipboard.
5.  **Success Path:** If validation passes, the system proceeds with the interactive, step-by-step execution of the plan.
6.  Upon completion, the system generates a final Markdown-formatted execution report, prints it to `stdout`, and copies it to the clipboard.

## 3. Acceptance Criteria (Scenarios)

### Scenario: Successful execution with `READ` action
- **Given** a valid plan is on the clipboard, containing a successful `READ` action.
- **When** the user runs `teddy execute` and approves all steps.
- **Then** the command should exit with a success code.
- **And** the final Markdown report printed to the console is also copied to the clipboard.
- **And** the report must contain a `## Resource Contents` section with the full, verbatim content of the file that was read.

**Example:**
- **Given** a plan on the clipboard contains:
  ````markdown
  ### `READ`
  - **Resource:** `hello.txt`
  ````
- **And** the file `hello.txt` contains "Hello, world!".
- **When** the plan is executed successfully.
- **Then** the final report must include a section similar to this:
  ````markdown
  ## Resource Contents
  The following resource contents were successfully read.
  ---
  **Resource:** `[hello.txt](/hello.txt)`
  ````text
  Hello, world!
  ````
  ---
  ````

### Scenario: Plan fails pre-flight validation
- **Given** a plan on the clipboard contains an `EDIT` action where the `FIND` block content does not exist in the target file.
- **When** the user runs `teddy execute`.
- **Then** the command should exit with a failure code before any actions are performed.
- **And** the output must be a Markdown report with `Overall Status: Validation Failed 🔴`.
- **And** the report must contain a `## Validation Errors` section detailing the failure.

**Example:**
- **Given** the file `hello.txt` contains `Hello, world!`
- **And** a plan on the clipboard contains:
  ````markdown
  ### `EDIT`
  - **File Path:** `hello.txt`

  #### `FIND:`
  ````text
  Goodbye, world!
  ````
  #### `REPLACE:`
  ````text
  Hello, TeDDy!
  ````
  ````
- **When** the plan is executed.
- **Then** the output must be a Markdown report similar to this:
  ````markdown
  # Execution Report: Validation Failed 🔴
  ...
  ## Validation Errors
  ### `EDIT` on `hello.txt`
  - **Error:** The `FIND` block could not be located in the file.
  ...
  ````

### Scenario: `EXECUTE` action fails during execution
- **Given** a valid plan on the clipboard contains an `execute` action with a command that produces a non-zero exit code.
- **When** the user approves and runs the action via `teddy execute`.
- **Then** the command should exit with a failure code.
- **And** the final report's overall status must be `Failed 🔴`.
- **And** the report must include a `## Failed Action Details` section with the `stdout`, `stderr`, and `return_code` of the failed command.

**Example:**
- **Given** a plan on the clipboard contains:
  ````markdown
  ### `EXECUTE`
  - **Description:** Run a failing command.
  ````shell
  ls non_existent_directory
  ````
  ````
- **When** the user approves and executes this action.
- **Then** the final report must include a section similar to this:
  ````markdown
  ## Failed Action Details
  ### `EXECUTE`
  - **Reason:** The command failed with a non-zero exit code.
  - **Return Code:** `1`
  - **`stdout`:**
    ````text

    ````
  - **`stderr`:**
    ````text
    ls: non_existent_directory: No such file or directory
    ````
  ````

### Scenario: `EDIT` action fails and reports file content
- **Given** a valid plan on the clipboard contains an `EDIT` action.
- **And** the `EDIT` action fails during execution for a reason other than validation (e.g., file permissions).
- **When** the user runs `teddy execute`.
- **Then** the command should exit with a failure code.
- **And** the report must include a `## Failed Action Details` section.
- **And** this section must contain the full, current content of the file that the `EDIT` action failed to modify.

**Example:**
- **Given** `pyproject.toml` exists.
- **And** an `EDIT` action on it fails.
- **Then** the final report must include a section similar to this:
  ````markdown
  ## Failed Action Details

  ### `EDIT` on `pyproject.toml`
  - **Error:** Could not write to file due to permissions error.

  ### Resource Contents
  ---
  **Resource:** `[pyproject.toml](/pyproject.toml)`
  ````toml
  [tool.poetry]
  name = "teddy_executor"
  # ... (actual, current content of the file) ...
  ````
  ---
  ````

### Scenario: Plan contains an unsupported action (`INVOKE`, `MEMO`, etc.)
- **Given** a plan on the clipboard contains an unsupported action like `INVOKE` or `MEMO`.
- **When** the user runs `teddy execute`.
- **Then** the action should be skipped.
- **And** the final report should log the action with a status of `Skipped 🟡` and a reason that it is not supported in manual mode.

**Example:**
- **Given** a plan on the clipboard contains:
  ````markdown
  ### `MEMO`
  [+] The user prefers verbose logging.
  ````
- **When** the plan is executed.
- **Then** the action log in the report must contain an entry similar to this:
  ````markdown
  #### `MEMO`
  - **Status:** Skipped 🟡
  - **Execution:** Not Supported
  - **Details:** This action is not supported in non-interactive/manual execution mode.
  ````

## 4. Architectural Changes
This slice will introduce a pre-flight validation step and a new Markdown-based report formatting service. The following components will be created:

### New Ports
-   **`IPlanValidator` (Inbound Port):** Defines the contract for plan pre-flight validation. See [design document](../core/ports/inbound/plan_validator.md).
-   **`IMarkdownReportFormatter` (Outbound Port):** Defines the contract for formatting the execution report. See [design document](../core/ports/outbound/markdown_report_formatter.md).

### New Services
-   **`PlanValidator`:** Implements `IPlanValidator` using a Strategy pattern to check a plan's actions before execution. See [design document](../core/services/plan_validator.md).
-   **`MarkdownReportFormatter`:** Implements `IMarkdownReportFormatter` using the Jinja2 template engine. See [design document](../core/services/markdown_report_formatter.md).

### Modified Components
-   **`main.py` (CLI Adapter):** The `execute` command will be refactored to:
    1.  Invoke the `PlanValidator` service before execution.
    2.  Use the `MarkdownReportFormatter` service to generate the final report for `stdout` and the clipboard, replacing the legacy YAML output.
-   **Composition Root (`main.py`):** The new services will be instantiated and wired up using `punq`.

## 5. Scope of Work

This feature will be implemented by following a strict outside-in, Test-Driven Development (TDD) workflow. The work is broken down into two main slices.

### Slice 1: Implement Pre-flight Validation & Core Formatter

**Goal:** Replace the YAML report with a basic Markdown report and introduce the critical pre-flight validation gate.

-   **[ ] 1. Acceptance Test Setup:**
    -   Create a new test file: `tests/acceptance/test_markdown_reports.py`.
-   **[ ] 2. Test & Implement Plan Validation:**
    -   In the new test file, write a failing acceptance test for the **"Plan fails pre-flight validation"** scenario defined in the acceptance criteria.
    -   Implement the `PlanValidator` service by following a TDD approach with unit tests in `tests/unit/core/services/test_plan_validator.py`. The service must implement all checks defined in the canonical **[Plan Validation Specification](../../specs/plan-format-validation.md)**.
        -   Reference: [`PlanValidator` Design Doc](../core/services/plan_validator.md)
    -   Refactor the `execute` command in `src/teddy_executor/main.py` to use the new `PlanValidator` service. Wire up the dependency in the composition root.
    -   Ensure the acceptance test now passes.
-   **[ ] 3. Test & Implement Core Markdown Formatter:**
    -   In `tests/acceptance/test_markdown_reports.py`, write a failing acceptance test for a successful execution that asserts the output is a basic Markdown report (verifying the summary table).
    -   Implement the `MarkdownReportFormatter` service using TDD in `tests/unit/core/services/test_markdown_report_formatter.py`.
        -   Reference: [`MarkdownReportFormatter` Design Doc](../core/services/markdown_report_formatter.md)
    -   Refactor the `execute` command in `src/teddy_executor/main.py` to use the new formatter service, completely replacing the old YAML report generation.
    -   Ensure the acceptance test now passes.

---
### Slice 2: Implement Manual Workflow Report Enhancements

**Goal:** Enhance the Markdown report with the specific sections required for a smooth manual, copy-paste workflow.

-   **[ ] 1. Test & Implement `Resource Contents` Section:**
    -   Write a failing acceptance test for the **"Successful execution with `READ` action"** scenario, asserting that the report contains the `## Resource Contents` section with the full file content.
    -   Enhance the `MarkdownReportFormatter` and the `execute` command logic to gather and correctly format the content from successful `READ` actions.
    -   Ensure the acceptance test now passes.
-   **[ ] 2. Test & Implement `Failed Action Details` Section:**
    -   Write a failing acceptance test for the **"`EDIT` action fails and reports file content"** scenario.
    -   Enhance the `ExecutionOrchestrator` and `main.py` to capture detailed failure information, including reading file content when `CREATE` or `EDIT` actions fail.
    -   Enhance the `MarkdownReportFormatter` to correctly format the `## Failed Action Details` section.
    -   Ensure the acceptance test now passes.
-   **[ ] 3. Test & Implement Handling of Unsupported Actions:**
    -   Write a failing acceptance test for the **"Plan contains an unsupported action"** scenario.
    -   Enhance the `ExecutionOrchestrator` to identify and gracefully skip unsupported actions (`INVOKE`, `CONCLUDE`, `MEMO`).
    -   Enhance the `MarkdownReportFormatter` to correctly report these actions as "Skipped".
    -   Ensure the acceptance test now passes.

---
## 6. Implementation Notes

-   **Parser Implementation Debt:** During analysis, a critical discrepancy was found between the official `new-plan-format.md` specification and the current `MarkdownPlanParser` implementation for `EDIT` actions.
    -   **The Spec:** The spec correctly defines `FIND:` and `REPLACE:` blocks using Level 4 (`####`) headings. The `PlanValidator` service was implemented correctly against this spec.
    -   **The Bug:** The `MarkdownPlanParser` contains legacy logic that incorrectly looks for `Paragraph` nodes instead of `Heading` nodes.
    -   **The Flow:** The execution flow in `main.py` is `parse -> validate`. The validator receives the malformed `Plan` object from the parser and performs its logical checks, which is why the structural error is not caught.
    -   **The Fix:** This should be remediated at the **end of Slice 2**. The fix involves updating the `_parse_edit_action` method in `src/teddy_executor/core/services/markdown_plan_parser.py` to correctly identify `Heading` nodes with `level == 4`.
