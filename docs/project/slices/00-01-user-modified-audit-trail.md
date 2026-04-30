# Slice: User Modification Audit Trail

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [report-format.md](../specs/report-format.md)

## Business Goal
Improve transparency and auditability when a user deviates from an AI-generated plan. By tracking specific modified fields and removing the restrictive "concise" reporting mode, we ensure the AI (and the human) can clearly see what changed in the execution phase without overwhelming the report with diffs.

## Scenarios

> As a developer, I want to see exactly which action parameters I modified in the TUI so that the execution report provides a clear audit trail of plan deviations.
```gherkin
Feature: User Modification Audit Trail

  Scenario: Tracking specific field modifications in the TUI
    Given a plan with an "EXECUTE" action:
      | command | ls -la |
    When I use the TUI to change the "command" to "ls -R"
    And I execute the plan
    Then the Action Log header for that action should include "(user modified: command)"
    And the ExecutionReport should store "command" in the "modified_fields" list for that action

  Scenario: Deprecating concise mode
    Given an execution report is generated
    When the report is formatted for Markdown
    Then the "Original Action Plan" and "Rationale" sections should be omitted (as they are now redundant with plan.md)
    And the formatter should no longer accept or respect an "is_concise" flag
```

## Deliverables
- [x] **Logic** - Add `modified_fields: list[str]` to `ActionData` (plan.py) and `ActionLog` (execution_report.py).
- [x] **Harness** - Update TUI event handlers to append field names to `modified_fields` whenever a parameter is successfully edited in the `ReviewerApp`.
- [x] **Refactor** - Remove `is_concise` from `IMarkdownReportFormatter` and `MarkdownReportFormatter`.
- [x] **Refactor** - Remove `is_concise` from `ExecutionReportAssembler` and any internal calls in the `ExecutionOrchestrator` or CLI handlers.
- [x] **Logic** - Update `execution_report.md.j2` to:
    - Remove the `is_concise` conditional blocks for Metadata, Rationale, and Original Plan (pruning these sections entirely).
    - Update the Action Log header to show `(user modified: field1, field2)` if `modified_fields` is not empty.
- [x] **Cleanup** - Prune the `render_original_plan` and `render_rationale` macros from the Jinja template if they are no longer used.
- [x] **Cleanup** - Perform a global `git grep "is_concise"` to verify total elimination from the codebase (including tests, mocks, and legacy adapters).

## Delta Analysis
- **Domain:** `ActionData` and `ActionLog` are the primary state containers.
- **TUI:** The `textual_plan_reviewer_previews.py` and associated logic already set `action.modified = True`. This logic must be expanded to track which specific key was changed.
- **Reporting:** `MarkdownReportFormatter` is the central point of change for the `is_concise` removal.

## Guidelines for Implementation
- Use the `TestEnvironment` to mock the TUI review process and verify that the resulting `ExecutionReport` contains the expected `modified_fields`.
- Ensure that the "user modified" string only appears if modifications actually occurred.
- When removing `is_concise`, ensure all tests that currently pass `is_concise=False` or `is_concise=True` are updated to match the new simplified signature.

## Implementation Notes
### Deliverable 1: Logic - modified_fields addition
- Added `modified_fields: list[str]` to both `ActionData` (mutable, used during modification) and `ActionLog` (frozen, used for reporting).
- Integrated assertions into existing domain model unit tests.
- Verified that default values (empty lists) maintain backward compatibility with the existing 660+ tests.

### Deliverable 2: Harness - TUI Modified Fields
- Updated `textual_plan_reviewer_helpers.py`, `textual_plan_reviewer_previews.py`, and `textual_plan_reviewer_editor.py` to track granular field modifications.
- Implemented tracking for: `command`, `queries`, `path`, `content`, `edits`, and `user_response`.
- Ensured `handle_revert` clears the `modified_fields` list.
- Identified technical debt: `ReviewerApp` does not support constructor injection for `EditSimulator`.

### Deliverable 3: Refactor - IMarkdownReportFormatter is_concise removal
- Removed `is_concise` parameter from `IMarkdownReportFormatter.format` and `MarkdownReportFormatter.format`.
- Updated `execution_report.md.j2` to remove `is_concise` logic and prune redundant sections (Rationale, Original Plan, Metadata) by default.
- Updated `textual_plan_reviewer_execution.py` to remove the deprecated parameter.
- Refactored `test_markdown_report_formatter_enhancements.py` to assert pruning behavior.
- Verified system integrity with 667 global tests passing.

### Deliverable 4: Refactor - Core is_concise removal
- Verified that `ExecutionReportAssembler` and `ExecutionOrchestrator` implementations and Port interfaces were already clean of `is_concise`.
- Updated `test_report_formats_integration.py` to remove legacy "concise" terminology and assert the new standard pruning behavior.
- Removed `is_concise` from `pyproject.toml` (Vulture ignore list).
- Confirmed zero occurrences of `is_concise` in `src/` via `git grep`.

### Deliverable 5 & 6: Logic & Cleanup - Template Updates
- Updated `execution_report.md.j2` to implement the detailed `(user modified: field1, field2)` audit trail.
- Pruned `Rationale`, `Original Plan Metadata`, and `Original Action Plan` sections from the rendered report to reduce redundancy and improve AI readability.
- Deleted unused macros: `render_rationale`, `render_metadata`, and `render_original_plan`.
- Verified changes with 669 passing tests, ensuring no regressions in report generation across the suite.

### Deliverable 7: Cleanup - is_concise Elimination
- Performed a global `git grep` and removed stale `is_concise` references from `docs/architecture/`, `docs/project/milestones/`, and `docs/project/specs/`.
- Verified that implementation (`src/`) is entirely clean of the parameter.
- Maintained a regression test in `test_markdown_report_formatter_enhancements.py` to ensure the flag does not leak back into the template context.
- Completed As-Built updates for `docs/architecture/core/domain/execution_report.md` and `docs/architecture/core/domain_model.md` to document the new `modified_fields` attribute.
