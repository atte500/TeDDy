# Bug: Abort Handling & Session Termination

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)

## Symptoms
1. Empty response after abort prompts for instructions again instead of quitting.
2. Messages provided in TUI are ignored if the plan is aborted/rejected.
3. Empty response does not consistently terminate the session loop.

## Context & Scope
### Regressing Delta
TBD - Likely in `SessionOrchestrator`, `SessionLifecycleManager`, or `ExecutionOrchestrator`.

### Environmental Triggers
Interactive session mode (`teddy start` or `teddy resume`).

### Ruled Out
TBD

## Diagnostic Analysis
### Causal Model
1. User aborts a plan in the TUI or CLI.
2. `ExecutionOrchestrator.execute` detects the abort and returns an `ABORTED` report.
3. `SessionOrchestrator.execute` receives the report and calls `_handle_aborted_session`.
4. `_handle_aborted_session` prompts for instructions. If empty, it returns the report as-is.
5. `SessionOrchestrator` then calls `lifecycle_manager.finalize_turn(report)`.
6. `finalize_turn` persists the report and calls `session_service.transition_to_next_turn`.
7. The session is now in a new turn with state `EMPTY`.
8. The CLI loop (`session_cli_handlers.py`) sees a report was returned, so it continues.
9. It calls `orchestrator.resume` again.
10. `SessionLifecycleManager.resume` sees state `EMPTY` and calls `session_planner.trigger_new_plan`.
11. Since the CLI loop cleared the `message` after the first turn, the planner prompts "Enter your instructions for the AI".

### Discrepancies
- [ ] Observation: Empty response in `_handle_aborted_session` returns report, but CLI loop continues. (resolved: The loop only stops if `resume` returns `None`)
- [ ] Observation: `SessionLifecycleManager.resume` prompts for instructions if no message is present, even after abort. (resolved: This is because `finalize_turn` transitions to a new EMPTY turn even on abort)
- [ ] Observation: Messages provided in TUI are ignored if the plan is aborted/rejected. (resolved: `ReviewerApp` does not harvest message on cancel, and `ExecutionOrchestrator` returns early without checking for metadata)
- [ ] Observation: `SessionOrchestrator` prompts for instructions even if one was already provided (e.g. in TUI). (resolved: `_handle_aborted_session` does not check `report.user_request`)

### Investigation History
- Initial discovery of `_handle_aborted_session` in `SessionOrchestrator`.

## Solution
### Implemented Fixes
- **TUI Layer**: Updated `ReviewerApp.action_cancel` to harvest the `_user_message_cache` into `plan.metadata["user_request"]` before exiting.
- **Orchestration Layer**: Updated `ExecutionOrchestrator._handle_aborted_execution` to pull the `user_request` from plan metadata if not provided as an argument.
- **Session Layer**: Updated `SessionOrchestrator._handle_aborted_session` to bypass the "How do you want to proceed?" prompt if a message already exists in the report.
- **Termination Logic**: Fixed `SessionOrchestrator._handle_aborted_session` to return `None` if the final message is empty, allowing the CLI loop to terminate gracefully.

### Prevention
- Added `tests/suites/unit/core/services/test_abort_logic_regression.py` containing three unit tests covering:
    - Session termination on empty abort response.
    - Respecting existing messages on abort (avoiding re-prompt).
    - Message propagation from plan metadata in `ExecutionOrchestrator`.
