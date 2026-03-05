# Slice 3: Refactor Execution Report Template

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

## 7. Deliverables

This checklist outlines the components required to support multi-modal reporting.

### 1. Enhanced Domain & Ports

1.  [ ] **Enhanced `Plan` and `ExecutionReport` domain models** capable of persisting rationale and original action data.
2.  [ ] **Updated `MarkdownPlanParser`** supporting the extraction of plan rationale.
3.  [ ] **Updated `IMarkdownReportFormatter` port contract** supporting the new `is_concise` toggle.

### 2. Orchestration & Flow

4.  [ ] **Updated `ExecutionOrchestrator`** ensuring complete data flow (rationale, actions) from Plan to ExecutionReport.

### 3. Modular Reporting System (Template)

5.  [ ] **Refactored `execution_report.md.j2` template** utilizing modular macros (`render_header`, `render_rationale`, `render_original_plan`, `render_resource`).
6.  [ ] **Multi-modal reporting logic** within the template to branch between CLI (concise) and Session (comprehensive) outputs.

### 4. Verification & Quality Assurance

7.  [ ] **Implementer logic for `MarkdownReportFormatter`** satisfying the updated port signature and template requirements.
8.  [ ] **Updated unit test suites** for parser and formatter validating the correct extraction and rendering of all report modes.
9.  [ ] **Verified report consistency** through manual CLI showcase verification.
