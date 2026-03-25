# 00-03: Include Git Status in Context Payload
- **Status:** Planned
- **Milestone:** N/A (Fast-Track)
- **Specs:** [Context Payload Format](/docs/project/specs/context-payload-format.md)

## Business Goal
Enhance the context payload with the current Git working state to give AI agents immediate awareness of modified, staged, and untracked files. This improves the AI's ability to understand the current progress within a session.

## Acceptance Criteria

### Scenario 1: Generating the Context Payload (`teddy context`)
#### Deliverables
- [✓] **Contract:** Update the `ProjectContext` domain model to include an optional `git_status` string field.
- [✓] **Contract:** Extend `IEnvironmentInspector` (or a more appropriate outbound port) to define a `get_git_status()` method.
- [✓] **Implementation:** Implement the `get_git_status()` method in `SystemEnvironmentInspector` using `subprocess` to call `git status -s`. Ensure it degrades gracefully (e.g., returns a specific string or `None`) if `git` is not installed or the directory is not a git repository.
- [✓] **Implementation:** Update `ContextService` to fetch the git status and populate it in the `ProjectContext`.
- [✓] **Implementation:** Update the markdown formatting logic (likely in `ContextService` or `MarkdownReportFormatter`) to render the `## 2. Git Status` section as defined in the spec.
- [✓] **Test:** Add or update acceptance tests (e.g., `tests/suites/acceptance/test_context_command_refactor.py`) to verify that the `teddy context` output includes the expected git status section when run within a git repository.
- [ ] **Test:** Ensure the `ReportParser` observer in the test harness correctly parses the new section if the context payload structure is part of its domain.

## Architectural Changes
- **Production Components:**
  - `ProjectContext` (Domain Model)
  - `IEnvironmentInspector` (Port)
  - `SystemEnvironmentInspector` (Adapter)
  - `ContextService` (Service)
- **Test Components:**
  - `CliTestAdapter` / Acceptance Tests (Driver)
  - `ReportParser` (Observer - if applicable to context payloads)

## Technical Debt
- [✓] Transferred to [Milestone 10](/docs/project/milestones/10-interactive-session-and-config.md).
