# Slice 33: Report Generation Enhancements

## 1. Business Goal
To enhance the `teddy` execution report generator by improving clarity, robustness, and the user experience. This involves refactoring the template file structure, ensuring validation error messages render correctly, and making reports more compact.

## 2. Architectural Changes

### Template File Rename
The canonical Jinja2 template will be renamed to more accurately reflect its purpose as a unified report generator.

-   **Old Path:** `src/teddy_executor/core/services/templates/concise_report.md.j2`
-   **New Path:** `src/teddy_executor/core/services/templates/execution_report.md.j2`

## 3. Scope of Work

### 3.1. Refactor Template and Documentation
-   [ ] **Rename Template File:** Rename `concise_report.md.j2` to `execution_report.md.j2`.
-   [ ] **Update Service:** Update the `get_template()` call in `markdown_report_formatter.py` to use the new template name.
-   [ ] **Update Documentation (Service):** Update `docs/core/services/markdown_report_formatter.md` to reference the new template name.
-   [ ] **Update Documentation (Spec):** Update `docs/specs/report-format.md` to reference the new template name.

### 3.2. Enhance Jinja2 Template (`execution_report.md.j2`)
-   [ ] **Add Smart Fencing:** Modify the `Validation Errors` section to apply the `| fence` filter to the content of `FIND` blocks within error messages.
-   [ ] **Tweak `chat_with_user` Report:** Remove the AI's initial prompt from the report. The "User Response" section is sufficient.
-   [ ] **Tweak `invoke`/`return` Report:** In the `render_action_details` macro, remove the generic "Details" line for `INVOKE` and `RETURN` actions.
-   [ ] **Add `EXECUTE` Failure Hint:** When an `EXECUTE` action fails, add a standardized hint to the report: "Hint: make sure to handle any regressions one by one decomposing them into unit / integration tests".

## 4. Acceptance Criteria

### Scenario 1: Smart Fencing for Validation Errors
-   **Given** a plan contains an `EDIT` action with a `FIND` block that includes backticks (e.g., "```python").
-   **And** the `FIND` block does not exist in the target file.
-   **When** `teddy execute` is run on the plan.
-   **Then** the command should terminate with a validation error.
-   **And** the validation error report should correctly display the `FIND` block, wrapped in a Markdown code fence that has more backticks than the content (e.g., "````").

### Scenario 2: Report for `chat_with_user`
-   **Given** a plan containing a `chat_with_user` action is executed successfully.
-   **When** the report is generated.
-   **Then** the report's action log for `chat_with_user` should contain the "User Response" section.
-   **But** it should **not** contain the original AI prompt.

### Scenario 3: Report for `invoke`
-   **Given** a plan containing an `invoke` action is executed successfully.
-   **When** the report is generated.
-   **Then** the report's action log for `invoke` should **not** contain the generic "- **Details:** ..." line.

### Scenario 4: Failed `EXECUTE` action includes a hint
-   **Given** a plan with an `EXECUTE` action that is guaranteed to fail (e.g., `exit 1`).
-   **When** the plan is executed.
-   **Then** the execution report for that action should contain the hint: "Hint: make sure to handle any regressions one by one decomposing them into unit / integration tests".
