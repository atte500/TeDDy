# Slice 03: Implement `SKIPPED` Run Status

**Source Brief:** (N/A - Generated from handoff technical debt from Slice 02)

## 1. Business Goal
To improve the semantic accuracy of the execution reports by correctly identifying and reporting when a plan's execution results in all actions being skipped by the user. This enhances the tool's feedback loop for both human users and AI agents.

## 2. Interaction Sequence
1.  The user provides a valid plan to the `teddy execute` command.
2.  During the interactive approval loop, the user chooses to skip every action in the plan.
3.  Upon completion, the system generates a final Markdown-formatted execution report.
4.  The report's `Overall Status` correctly shows `Skipped`.

## 3. Acceptance Criteria (Scenarios)

### Scenario: Plan where all actions are skipped reports "Skipped" status
- **Given** a valid plan with one or more actions.
- **When** the user runs `teddy execute` and skips every action.
- **Then** the command should exit with a success code.
- **And** the final Markdown report's `Overall Status` must be `Skipped`.

## 4. Architectural Changes

### Modified Components
-   **`ExecutionReport` (Domain Model):** The `RunStatus` enum will be updated to include a `SKIPPED` member.
-   **`main.py` (CLI Adapter):** The logic for determining the overall run status will be updated to handle the "all skipped" case.
-   **`MarkdownReportFormatter`:** The formatter will be updated to correctly render the `Skipped` status string in the report header.

## 5. Scope of Work

-   **[ ] 1. Create Failing Acceptance Test:**
    -   Add a new scenario to `tests/acceptance/test_markdown_reports.py` that simulates a user skipping all actions and asserts the report shows `Overall Status: Skipped`.
-   **[ ] 2. Update Domain Model:**
    -   Add `SKIPPED` to the `RunStatus` enum in `src/teddy_executor/core/domain/models/execution_report.py`.
-   **[ ] 3. Update Execution Logic:**
    -   Refactor the status calculation logic in `src/teddy_executor/main.py` to correctly identify the "all skipped" condition.
-   **[ ] 4. Update Report Formatter:**
    -   Update the `MarkdownReportFormatter` to handle the new `SKIPPED` status.
