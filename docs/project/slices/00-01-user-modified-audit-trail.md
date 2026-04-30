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
- [ ] **Harness** - Update TUI event handlers to append field names to `modified_fields` whenever a parameter is successfully edited in the `ReviewerApp`.
- [ ] **Refactor** - Remove `is_concise` from `IMarkdownReportFormatter` and `MarkdownReportFormatter`.
- [ ] **Refactor** - Remove `is_concise` from `ExecutionReportAssembler` and any internal calls in the `ExecutionOrchestrator` or CLI handlers.
- [ ] **Logic** - Update `execution_report.md.j2` to:
    - Remove the `is_concise` conditional blocks for Metadata, Rationale, and Original Plan (pruning these sections entirely).
    - Update the Action Log header to show `(user modified: field1, field2)` if `modified_fields` is not empty.
- [ ] **Cleanup** - Prune the `render_original_plan` and `render_rationale` macros from the Jinja template if they are no longer used.
- [ ] **Cleanup** - Perform a global `git grep "is_concise"` to verify total elimination from the codebase (including tests, mocks, and legacy adapters).

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
