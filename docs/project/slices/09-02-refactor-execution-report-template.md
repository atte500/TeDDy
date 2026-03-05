# Slice 2: Refactor Execution Report Template

## 1. Business Goal

To provide distinct report formats for the two primary TeDDy workflows: a concise, self-contained **CLI Report** for manual, clipboard-driven use, and a comprehensive, auditable **Session Report** for the stateful, interactive workflow.

-   **Source Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/09-interactive-session-and-config.md)

## 2. Interaction Sequence

1.  **Plan Execution:** A plan is executed via the `ExecutionOrchestrator`.
2.  **Report Generation:** The orchestrator requests a report from the `IMarkdownReportFormatter`, specifying whether it should be concise.
3.  **Formatting:** The formatter applies branching logic within the Jinja2 template to render either the "CLI" or "Session" format.
4.  **Delivery:** The resulting Markdown is returned to the user (via clipboard/stdout for CLI, or written to a file for Session).

## 3. Preliminary Refactoring

To support the new report formats, several core contracts must be updated to ensure the necessary data is preserved throughout the execution lifecycle.

1.  **Domain Model Updates:**
    -   `Plan`: Add a `rationale: str` field.
    -   `ExecutionReport`: Add `rationale: str` and `original_actions: Sequence[ActionData]` fields.
2.  **Port Update:**
    -   `IMarkdownReportFormatter.format()`: Update signature to accept `is_concise: bool`.
3.  **Service Updates:**
    -   `MarkdownPlanParser`: Extract and store the rationale content during parsing.
    -   `ExecutionOrchestrator`: Transfer the `rationale` and `original_actions` from the `Plan` to the `ExecutionReport`.

## 4. Acceptance Criteria (Scenarios)

### Scenario: CLI Report (Concise) focuses on immediate action

-   **Given** an `ExecutionReport` resulting from a plan that included a successful `READ` action and a failed `CREATE` action.
-   **When** the report is formatted with `is_concise=True`.
-   **Then** the output MUST NOT contain the original plan's Rationale section.
-   **And** the output MUST NOT contain the original Action Plan summary.
-   **And** the output MUST contain the full, verbatim content of the successful `READ` action.
-   **And** the output MUST contain the current content of the file where the `CREATE` action failed.

### Scenario: Session Report (Comprehensive) focuses on audit trail

-   **Given** an `ExecutionReport` resulting from a plan with a Rationale and several actions.
-   **When** the report is formatted with `is_concise=False`.
-   **Then** the output MUST contain the original plan's Rationale section.
-   **And** the output MUST contain a summary of the original Action Plan.
-   **And** the output MUST NOT contain the full content of successful `READ` actions (as this is managed by the session's context system).

## 5. User Showcase

### Verify CLI Report (via `teddy execute --no-copy`)

1.  Create a simple plan with a `READ` action and a `Rationale`.
2.  Run `poetry run teddy execute --no-copy --plan-file plan.md`.
3.  **Expected Result:** The output in the terminal should be concise, omitting the rationale but including the content of the file that was read.

### Verify Session Report (Internal Logic)

*Note: Since the session command is not yet fully implemented, this is verified via integration tests.*

1.  Run the integration test suite: `poetry run pytest tests/integration/core/services/test_markdown_report_formatter.py`.
2.  **Expected Result:** The tests should verify that the `is_concise=False` flag produces a report containing the rationale and original action plan.

## 6. Architectural Changes

The approved architecture introduces a modular, macro-based reporting system to support multi-modal output.

-   **Domain Layer:**
    -   [Plan](/docs/architecture/core/domain_model.md): Enhanced to preserve the `rationale`.
    -   [ExecutionReport](/docs/architecture/core/domain/execution_report.md): Enhanced to preserve `rationale` and `original_actions`.
-   **Ports Layer:**
    -   [IMarkdownReportFormatter](/docs/architecture/core/ports/outbound/markdown_report_formatter.md): Updated to support the `is_concise` toggle.
-   **Services Layer:**
    -   [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md): Updated to capture the rationale content.
    -   **MarkdownReportFormatter:** Refactored to use Jinja2 macros for modular layout.

## 7. Scope of Work

### 1. Preliminary Refactoring: Domain & Parser

1.  [ ] **Update `Plan` Model:** Add the `rationale: str` field to `src/teddy_executor/core/domain/models/plan.py`.
2.  [ ] **Update `ExecutionReport` Model:** Add `rationale: str | None` and `original_actions: Sequence[ActionData]` to `src/teddy_executor/core/domain/models/execution_report.py`.
3.  [ ] **Update `MarkdownPlanParser`:** Modify `_parse_strict_top_level` in `src/teddy_executor/core/services/markdown_plan_parser.py` to extract the content of the Rationale block and pass it to the `Plan` constructor.
4.  [ ] **Update Port:** Update `IMarkdownReportFormatter.format()` in `src/teddy_executor/core/ports/outbound/markdown_report_formatter.py` to accept `is_concise: bool = True`.

### 2. Orchestration

5.  [ ] **Update `ExecutionOrchestrator`:** Modify `execute()` in `src/teddy_executor/core/services/execution_orchestrator.py` to:
    -   Pass the plan's `rationale` and `actions` to the `ExecutionReport` constructor.
    -   *Note: For now, the call to `report_formatter.format()` can continue to use the default `is_concise=True`.*

### 3. Template Refactoring (Modular Macros)

6.  [ ] **Refactor `execution_report.md.j2`:**
    -   Extract the header logic into a `render_header` macro.
    -   Create a `render_rationale` macro (conditional on `not is_concise`).
    -   Create a `render_original_plan` macro (conditional on `not is_concise`).
    -   Isolate the `Action Log` rendering into a dedicated, robustly delimited section.
    -   Update `render_resource` logic to embed successful `READ` content only when `is_concise=True`.

### 4. Verification

7.  [ ] **Update Service:** Update `MarkdownReportFormatter.format()` in `src/teddy_executor/core/services/markdown_report_formatter.py` to implement the new signature and pass `is_concise` to the template.
8.  [ ] **Unit Tests:**
    -   Update `tests/unit/core/services/test_markdown_plan_parser.py` to verify rationale extraction.
    -   Update `tests/unit/core/services/test_markdown_report_formatter.py` to verify both CLI and Session output formats.
9.  [ ] **Manual Verification:** Perform the steps in the **User Showcase** to confirm the CLI output remains concise and functional.
