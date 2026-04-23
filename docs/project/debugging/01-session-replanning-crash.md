# Bug: Session Replanning Crash with Empty Error

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
When a plan validation fails during a session, the system logs "Validation failed... replanning", receives an AI response, but then crashes with "Error: " (empty error message). The AI response is saved to the session folder, but the session terminates.

## Context & Scope
### Regressing Delta
Recent refactors in `src/teddy_executor/core/services/session_orchestrator.py` (commits `77524fe` and `f4bc069`) reverted architecture to synchronous and modified the workflow.

### Environmental Triggers
- Active session (`teddy session`).
- A plan that fails validation (e.g., malformed Markdown or invalid action parameters).
- LLM provides a "replan" response.

### Ruled Out
- LLM API failure (user states AI response is received and written to folder).

## Diagnostic Analysis
### Causal Model
1. `SessionOrchestrator` detects validation failure in a generated plan.
2. It triggers `lifecycle_manager.trigger_replan`, which correctly performs the LLM replan and creates the next turn directory.
3. `SessionOrchestrator` returns the `VALIDATION_FAILED` execution report from the original failed plan.
4. The CLI session handler (`session_cli_handlers.py`) receives the report and calls `handle_report_output`.
5. `handle_report_output` (in `cli_helpers.py`) raises `typer.Exit(code=1)` because the report status is `VALIDATION_FAILED`.
6. The session handler's outer `try...except` catches the `Exit` exception.
7. Since `typer.Exit` has an empty string representation, the handler prints `Error: ` and terminates the process, preventing the loop from continuing to the next turn. (resolved: confirmed via analysis of `cli_helpers.py` and session handlers)

### Discrepancies
- None yet.

### Investigation History
- Found log strings in `session_orchestrator.py` and `session_cli_handlers.py`.
- Identified recent refactoring in `session_orchestrator.py`.

## Solution
### Implemented Fixes
- Modified `handle_report_output` in `cli_helpers.py` to accept an `exit_on_failure` parameter (default `True`).
- Updated `session_cli_handlers.py` to set `exit_on_failure=False`, allowing session loops to continue after validation failures.
- Centralized the yellow "[yellow]Validation failed... replanning[/yellow]" notification in `SessionLifecycleManager.trigger_replan` to ensure it is always visible during re-plans.
- Aligned legacy acceptance tests (`test_ai_telemetry.py` and `test_session_management.py`) to expect successful process exits (`exit_code=0`) during session re-plan loops.

### Prevention
- Added `tests/suites/unit/adapters/inbound/test_session_replan_loop.py` which explicitly verifies that `handle_report_output` does not raise an exit exception when `exit_on_failure=False` is provided.
