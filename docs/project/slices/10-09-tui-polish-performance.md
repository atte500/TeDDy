# Slice 10-09: TUI Polish & Performance

- **Status:** Completed
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Business Goal
Improve the TUI's usability and reliability by fixing parameter formatting, showing missing metadata, and preventing UI freezes when handling large execution logs.

## Scenarios
> As a developer, I want a responsive and informative TUI so that I can efficiently review and execute complex AI plans.

### Scenario 1: Parameter Clarity & Completeness
Given a plan with a RESEARCH action and a PROMPT action with reference files
When I view the action details in the TUI
Then the RESEARCH queries should show as a clean comma-separated list
And the PROMPT action should show its "reference_files" parameter.

### Scenario 2: Large Log Resilience
Given an action that has executed and produced 10,000 lines of output
When I select that action in the TUI
Then the TUI should remain responsive
And the execution log should be formatted and potentially truncated for the preview.

### Scenario 3: Plan Context Visibility
Given a plan with a Rationale, Agent, and Plan Type
When the TUI opens
Then I should see a dedicated panel displaying this high-level context.

### Deliverables
- [x] **Logic** - Update `resolve_action_parameters` to format lists and include missing fields.
- [x] **Logic** - Implement `ActionLog` parsing/formatting logic (e.g., JSON pretty-printing).
- [x] **Harness** - Create a prototype demonstrating the new layout and log handling.
- [x] **Wiring** - Add `PlanSummary` widget to `ReviewerApp` and update CSS layout.
- [x] **Wiring** - Optimize `DetailItem` to handle large text payloads using `Static` or truncation.
- [x] **Cleanup** - Ensure `RESEARCH` edit logic matches the new display format.

## Delta Analysis
- **`textual_plan_reviewer_helpers.py`**: Update `resolve_action_parameters` for list formatting and field completeness.
- **`textual_plan_reviewer_app.py`**: Modify `compose` to include a summary header. Update CSS for 3-pane layout or header.
- **`textual_plan_reviewer_widgets.py`**: Add `PlanSummary` widget. Update `DetailItem` to use `Static` instead of `Label` for large content to improve performance.
- **`textual_plan_reviewer_logic.py`**: Update `_update_detail_view` to handle the new `PlanSummary`.

## Guidelines for Implementation
- Use `textual.widgets.Static` with `expand=True` for log details to avoid the performance overhead of `Label` on huge strings.
- Truncate extremely large logs (e.g., > 50KB) in the preview and add a "View Full Log" action.
