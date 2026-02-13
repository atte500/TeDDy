# Slice 02: Markdown Report Enhancements & Bug Fixes

**Source Brief:** (N/A - Generated from handoff technical debt)

## 1. Business Goal
To improve the accuracy, spec-compliance, and user experience of the Markdown execution reports by fixing a set of identified bugs and implementing key refactorings. This will increase the tool's reliability and maintainability.

## 2. Interaction Sequence
The core interaction sequence of `teddy execute` remains unchanged. This slice focuses on correcting the content and format of the final Markdown report that is printed to `stdout` and copied to the clipboard. The fixes will ensure the report is a more accurate and helpful feedback mechanism for the user and AI.

## 3. Acceptance Criteria (Scenarios)

### Scenario: `EXECUTE` action has a correct title in the report
- **Given** a plan with an `EXECUTE` action that has a `Description`.
- **When** the plan is executed.
- **Then** the final report's action log must show a heading for that action including the description (e.g., `#### `EXECUTE` on "Run a test command"`).

### Scenario: `READ` action shows the correct resource path
- **Given** a plan with a successful `READ` action.
- **When** the plan is executed.
- **Then** the final report's `## Resource Contents` section must correctly identify the resource path that was read (e.g., `**Resource:** [path/to/file.md](/path/to/file.md)`).

### Scenario: Failed `EDIT` action reports file content
- **Given** a plan with an `EDIT` action that will fail during execution (e.g., due to a permissions error).
- **When** the plan is executed.
- **Then** the final report must contain a `## Failed Action Details` section.
- **And** this section must include the full, current content of the file that the `EDIT` action failed to modify.

### Scenario: Report has no extra newlines
- **Given** a plan that passes pre-flight validation.
- **When** the plan is executed.
- **Then** the final report must not have a large gap of empty newlines before the `## Execution Summary` section.

## 4. Architectural Changes

### Modified Components
-   **`MarkdownReportFormatter`:** This service will be the primary focus of changes to fix the formatting, titles, and content of the report.
-   **`ExecutionOrchestrator`:** May require changes to correctly capture and pass failure data (like file contents) to the report formatter.
-   **`ConsoleInteractor`:** Will be refactored to handle the canonical `edits` list from the parser, removing data normalization logic from the `ExecutionOrchestrator`.
-   **Acceptance Tests:** Multiple tests will be refactored to use a more robust method for handling multi-line input.

## 5. Scope of Work

-   **[ ] 1. (Bugfix) `EXECUTE` action report title:** Fix the report to show the command description (e.g., `EXECUTE on "Run tests"`) instead of `EXECUTE on Unknown`.
-   **[ ] 2. (Bugfix) `READ` action resource contents:** Fix the report to show the correct resource path (e.g., `Resource: [README.md](/README.md)`) in the `## Resource Contents` section instead of `Resource: None`.
-   **[ ] 3. (Spec Compliance) Failure report for `CREATE`/`EDIT`:** When a `CREATE` or `EDIT` action fails, the report must include the full current content of the target file in the `## Failed Action Details` section, as required by the specification.
-   **[ ] 4. (Bugfix) Report formatting:** Remove the extra newlines that appear before the `## Execution Summary` section in the report.
    - **Note:** This only happens when validation passes.
-   **[ ] 5. (Refactor) Decouple Orchestrator:** Refactor the `ConsoleInteractor` to handle the canonical `edits` list from the parser, removing the data normalization logic from `ExecutionOrchestrator`.
-   **[ ] 6. (Refactor) Test Input Handling:** Improve acceptance tests to use a more robust method for providing multi-line input to the CLI runner (e.g., text blocks).
-   **[ ] 7. (Refactor) Report UX Polish:** Enhance the report formatter to present the `Details` field in a human-readable format instead of a raw dictionary string.
