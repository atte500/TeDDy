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
-   [x] **Rename Template File:** Rename `concise_report.md.j2` to `execution_report.md.j2`.
-   [x] **Update Service:** Update the `get_template()` call in `markdown_report_formatter.py` to use the new template name.
-   [x] **Update Documentation (Service):** Update `docs/architecture/core/services/markdown_report_formatter.md` to reference the new template name.
-   [x] **Update Documentation (Spec):** Update `docs/project/specs/report-format.md` to reference the new template name.

### 3.2. Enhance Jinja2 Template (`execution_report.md.j2`)
-   [x] **Add Smart Fencing:** Modify the `Validation Errors` section to apply the `| fence` filter to the content of `FIND` blocks within error messages.
-   [x] **Tweak `chat_with_user` Report:** Remove the AI's initial prompt from the report. The "User Response" section is sufficient.
-   [x] **Tweak `invoke`/`return` Report:** In the `render_action_details` macro, remove the generic "Details" line for `INVOKE` and `RETURN` actions.

### 3.3. Implement Dynamic Code-Block Language
-   [x] **Create Utility Function:** In `src/teddy_executor/core/utils/markdown.py`, create a new function `get_language_from_path(path: str) -> str` that maps common file extensions to language identifiers and falls back to using the extension itself if no map is found.
-   [x] **Register Jinja2 Filter:** In `src/teddy_executor/core/services/markdown_report_formatter.py`, import the new utility function and register it as a new Jinja2 filter named `language_from_path`.
-   [x] **Update Template:** In the Jinja2 template (`execution_report.md.j2`), modify the `render_resource` macro to use the new filter (`{{ path | language_from_path }}`) instead of the hardcoded `text` identifier.

## 5. Implementation Summary
- **Template Renaming:** The core reporting template was successfully renamed to `execution_report.md.j2` and all corresponding references and docs were updated.
- **Smart Fencing:** Updated `PlanValidator` to use the shared `get_fence_for_content` utility when constructing validation error strings involving `FIND` blocks or `diff` texts, making the CLI output robust and parseable.
- **Report Template Tweaks:** The `execution_report.md.j2` template was optimized: it now correctly suppresses the redundant original AI prompt for `CHAT_WITH_USER` actions and hides generic fallback details for `INVOKE` and `RETURN` blocks.
- **Dynamic Languages:** Created an exhaustive mapping utility `get_language_from_path` in `markdown.py`. This was exposed as a Jinja2 filter and applied to the report generator so that file contents display using proper markdown code languages instead of defaulting to `text`.
- **Architectural Note (T2 - User Request):** Handled a mid-stream request to apply the dynamic language feature to the `teddy context` payload as well. The `cli_formatter.py` was refactored to consume the new `get_language_from_path` utility, deleting duplicated logic and extending the exhaustive mapping to context generation. All logic is covered by new acceptance tests.

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

### Scenario 4: Dynamic Language in Code Blocks
-   **Given** a plan includes reading a file named `src/main.py`.
-   **And** another file named `config.cfg`.
-   **When** the plan is executed and the report is generated.
-   **Then** the report's "Resource Contents" for `src/main.py` should be enclosed in a ` ```python ` code block.
-   **And** the "Resource Contents" for `config.cfg` should be enclosed in a ` ```cfg ` code block.
