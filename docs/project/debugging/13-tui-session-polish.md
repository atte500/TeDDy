# Bug: TUI & Session Polish

- **Status:** Unresolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)

## Symptoms
1. **TUI Navigation:** Tab to move to the right panel does not work for rationale or context items.
2. **Context Removal:** `session.context` files manually struck through in the TUI are not removed from the session context.
3. **UI Content:** System view in right pane shows "Unknown" instead of the agent name.
4. **Terminal Spacing:** Missing empty lines before turn status and "MESSAGE from TeDDy".
5. **Terminal Color:** "Checking configurations..." has incorrect color (should be default).

## Context & Scope
### Regressing Delta
Multiple features introduced in Milestone 10 regarding Interactive Sessions and the Context Management UI.

### Environmental Triggers
Standard interactive session usage via `teddy start` or `teddy resume`.

### Ruled Out
- Non-interactive `execute` command (TUI issues).

## Diagnostic Analysis
### Causal Model
1. **Focus Navigation:** `ReviewerApp.action_focus_right` attempted to focus a non-focusable `ContentSwitcher`. Fixed by focusing the active child widget.
2. **Session Context Pruning:** `SessionService` only pruned from `turn.context`. Fixed by adding pruning logic for `session.context`.
3. **Agent Name:** `ContextService` did not receive `agent_name`. Fixed by updating the port and service to propagate the name from the planning/orchestration layer.
4. **Terminal Spacing:** Added leading newlines to `PlanningService` and `ConsoleInteractor` messages.
5. **Config Color:** Removed `fg` and `dim` styling from `_run_cli_preflight_check`.
6. **Section Navigation:** Refactored `ReviewerApp` jump logic to dynamically cycle through `CONTEXT_ROOT`, `RATIONALE_ROOT`, and `ACTION_PLAN_ROOT`.

### Discrepancies
- None yet.

### Investigation History
1. Initial report of 5 polish items.
