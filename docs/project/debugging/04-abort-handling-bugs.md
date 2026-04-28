# Bug: Abort Handling & Session Termination

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../../milestones/10-interactive-session-and-config.md)

## Symptoms
1. Empty response after abort prompts for instructions again instead of quitting. (resolved)
2. Messages provided in TUI are ignored if the plan is aborted/rejected. (resolved)
3. Empty response does not consistently terminate the session loop.
4. **NEW**: Jinja error `'dict object' has no attribute 'run_summary'` when quitting via empty response.
5. **NEW**: Intermittent failure to prompt for abort message (session continues to next turn automatically).

## Context & Scope
### Regressing Delta
TBD - Likely in `SessionOrchestrator`, `SessionLifecycleManager`, or `ExecutionOrchestrator`.

### Environmental Triggers
Interactive session mode (`teddy start` or `teddy resume`).

### Ruled Out
TBD

## Diagnostic Analysis
### Causal Model
1. User aborts a plan. `ExecutionOrchestrator` returns an `ABORTED` report.
2. `ExecutionReportAssembler` leaked the turn-starting `message` into `report.user_request`. (resolved: Now explicitly ignored in session logic)
3. `SessionOrchestrator._handle_aborted_session` saw this leaked message and skipped the abort prompt. (resolved: Now always prompts on abort)
4. If the user provided an empty response, `_handle_aborted_session` returned `None`.
5. `SessionOrchestrator.execute` passed this `None` to `finalize_turn`.
6. `MarkdownReportFormatter` crashed because the Jinja template expects a valid report object. (resolved: `execute` now guards against `None` reports)

### Discrepancies
- [ ] Observation: Empty response in `_handle_aborted_session` returns report, but CLI loop continues. (resolved: The loop only stops if `resume` returns `None`)
- [ ] Observation: `SessionLifecycleManager.resume` prompts for instructions if no message is present, even after abort. (resolved: This is because `finalize_turn` transitions to a new EMPTY turn even on abort)
- [ ] Observation: Messages provided in TUI are ignored if the plan is aborted/rejected. (resolved: `ReviewerApp` does not harvest message on cancel, and `ExecutionOrchestrator` returns early without checking for metadata)
- [ ] Observation: `SessionOrchestrator` prompts for instructions even if one was already provided (e.g. in TUI). (resolved: `_handle_aborted_session` does not check `report.user_request`)

### Investigation History
- Initial discovery of `_handle_aborted_session` in `SessionOrchestrator`.

## Solution
### Implemented Fixes
- **TUI Layer**: Updated `ReviewerApp.action_cancel` to harvest messages.
- **Orchestration Layer**: Updated `ExecutionOrchestrator` to propagate messages on abort.
- **Session Layer**: Fixed `SessionOrchestrator` to ignore leaked messages and ALWAYS prompt for instructions on abort, ensuring the user can redirect or quit.
- **Termination Logic**: Added a guard in `SessionOrchestrator.execute` to prevent passing `None` to `finalize_turn`, and added a "Session terminated" log for clarity.

### Prevention
- Added `tests/suites/unit/core/services/test_abort_handling_regression.py` covering the crash and the prompt logic.
