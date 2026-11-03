# Bug: TUI 'x'-Executed Actions Are Not Logged to Console on Plan Submission
- **Status:** Resolved
- **Milestone:** Milestone 4: Terminal User Interface
- **Vertical Slice:** N/A
- **Specs:** docs/project/specs/interactive-session-workflow.md

## Symptoms
Expected: When a plan is submitted after some actions were executed manually via the `x` (Execute Step) key in the TUI, the console shows a log line for every action — both the pre-executed ones and the ones executed during normal plan execution.

Actual: Actions executed via `x` run silently inside the TUI (stdout/stderr redirected, dispatcher logger raised to WARNING). When the plan is subsequently submitted, the console emits `CREATE - <desc>` / `SUCCESS`-style lines only for actions that were NOT pre-executed. The pre-executed actions appear in the execution report but produce no console output.

Minimal reproduction:
1. Start an interactive (non-YOLO) session that opens the TUI plan reviewer.
2. Press `x` on one or more actions to execute them manually.
3. Press `s` to submit the plan.
4. Observe the console: only the actions executed during submission print a log line; the actions executed via `x` print nothing.

## Context & Scope
### Regressing Delta
Not a single regressing commit. The behavior follows from two deliberately silent paths:
- `textual_plan_reviewer_execution._execute_silently` suppresses dispatcher output during `x`.
- `ExecutionOrchestrator._handle_action_in_loop` reuses `action.action_log` for `action.executed and action.action_log` with no console emission.

### Environmental Triggers
- Interactive (non-YOLO) session with the TUI plan reviewer.
- At least one action executed via `x` before submitting the plan.

### Ruled Out
- Console handler configuration: `logging.basicConfig(level=INFO, format="%(message)s", handlers=[StreamHandler(sys.stderr)])` in `__main__.py` renders `logger.info` lines normally for freshly dispatched actions.
- `ActionDispatcher` formatting: fresh actions correctly emit `{ACTION} - {description}` and the uppercase status.

## Diagnostic Analysis
### Causal Model
Two paths mutate `ActionData` state:
1. TUI `x`: `action_execute_step` -> `execute_step_logic` -> `orchestrate_execution` -> `_execute_silently(dispatcher, action)`, which sets the dispatcher logger to WARNING and redirects stdout/stderr into an `io.StringIO`. It then sets `action.executed = True` and `action.action_log = log`. Only MESSAGE replies are echoed via `emit_user_message`.
2. Submission: `ExecutionOrchestrator.execute` -> `_process_plan_actions` -> `_handle_action_in_loop`. An action with `executed=True` and a cached `action_log` is returned untouched with no console output. A not-yet-executed action proceeds through `_dispatch_single_action` -> `ActionExecutor.confirm_and_dispatch` -> `ActionDispatcher.dispatch_and_execute`, which emits the two `logger.info` lines.

Console output is therefore emitted only on the dispatch path and never for the cached pre-executed actions.

### Discrepancies
- [x] Expected console lines for pre-executed actions on submit; none observed. Confirmed by MRE at `spikes/debug/tui-executed-action-console-logging/01-tui-executed-action-missing-console-log-mre.py` and proven fixed in the sandbox replica `spikes/debug/tui-executed-action-console-logging/replica_execution_orchestrator.py`: with the two console lines added to the reuse branch, the pre-executed action emits `CREATE - created manually via x` / `SUCCESS` and the MRE reports `PASS -- FIX PROVEN`. Root cause: silent reuse branch in `_handle_action_in_loop`. (Resolved)

### Investigation History
1. Located the `x` binding (`textual_plan_reviewer_app.py:71`) and traced the TUI path to `_execute_silently`, which suppresses all dispatcher output.
2. Read `execution_orchestrator.py`, `action_dispatcher.py`, `action_executor.py`; identified the silent already-executed reuse branch in `_handle_action_in_loop` as the missing logging site.
3. Verified console logging wiring via `logging.basicConfig` in `__main__.py:48`.
4. Ran the MRE (`spikes/debug/tui-executed-action-console-logging/01-tui-executed-action-missing-console-log-mre.py`); observed an empty capture for the pre-executed action and `CREATE - fresh action` / `SUCCESS` for a fresh action, empirically reproducing the missing console output.
5. Confirmed the behavior is by design on both halves and not a regression from a single commit: TUI `x` runs through `_execute_silently` (logger raised to WARNING, stdout/stderr redirected) and the submit path reuses the cached log with no emission, so `git bisect` is not applicable.
6. Copied the production orchestrator to `spikes/debug/tui-executed-action-console-logging/replica_execution_orchestrator.py` and injected the two `logger.info` lines into the already-executed reuse branch; re-ran the MRE against the replica and observed `CREATE - created manually via x` / `SUCCESS` in the pre-executed capture, so the MRE reported `PASS -- FIX PROVEN`. This proves the fix without touching production code.
7. Ran the impact audit: `_handle_action_in_loop` has no callers outside `execution_orchestrator.py`; `ExecutionOrchestrator` is constructed at the composition root, by `SessionOrchestrator`, and in tests; no existing integration test asserts empty logging for the reuse branch. The fix stays a one-file production change and adds only the two console lines for pre-executed actions.
8. Applied the fix directly in `src/teddy_executor/core/services/execution_orchestrator.py` (new `_emit_preexecuted_console_log` helper invoked from the reuse branch) and added two regression tests in `tests/suites/integration/core/services/test_manual_execution_persistence.py`. `make test` passed with 2124 passed and 5 skipped, so the fix is resolved in production code rather than only in the sandbox replica.
9. Verified the fix cannot affect the open TUI: `_handle_action_in_loop` (and therefore `_emit_preexecuted_console_log`) is reached only from `_process_plan_actions`, which runs after `_perform_interactive_review` returns — i.e. after `ReviewerApp.run()` closes the reviewer. The TUI `x` path calls `ActionDispatcher.dispatch_and_execute` directly through `_execute_silently` and never touches `ExecutionOrchestrator`. A grep over `src/teddy_executor/adapters/inbound` finds no reference to the orchestrator, the reuse branch, or the new helper, so the added logging is inert while the plan reviewer is open and only fires on submit.

## Solution
### Root Cause
Verified via MRE and proven in the sandbox replica `spikes/debug/tui-executed-action-console-logging/replica_execution_orchestrator.py`. `ExecutionOrchestrator._handle_action_in_loop` returns the cached `action.action_log` for actions already executed via TUI `x` without emitting the console log lines that `ActionDispatcher.dispatch_and_execute` emits for freshly dispatched actions (`{ACTION} - {description}` and the uppercase status). The TUI `x` path is intentionally silent, so the only place a submitted plan can announce a pre-executed action is the orchestrator's reuse branch. The proven fix adds those two `logger.info` lines (skipping `MESSAGE` actions) to the reuse branch. It was applied directly in `src/teddy_executor/core/services/execution_orchestrator.py` via the new `_emit_preexecuted_console_log` helper, called from the already-executed reuse branch in `_handle_action_in_loop`. Regression tests were added in `tests/suites/integration/core/services/test_manual_execution_persistence.py` (`test_manually_executed_action_logs_on_submit` asserts the two lines; `test_manually_executed_message_action_stays_silent` asserts `MESSAGE` reuse stays quiet). `make test` passes (2124 passed, 5 skipped).

### Affected Components
- `ExecutionOrchestrator`: silent already-executed reuse branch (`_handle_action_in_loop`). Resolved directly in `src/` by adding the `_emit_preexecuted_console_log` helper, so pre-executed actions are announced on submit.
- `ActionDispatcher`: source of the canonical console log lines (`{ACTION} - {description}` plus uppercase status) that the fix must mirror for consistency.
- `Milestone 6 (Cross-Cutting Consolidation)`: the inline fix duplicates the dispatcher's log-format strings and `MESSAGE` detection. Extracting a shared `log_action_outcome(action_name, description, status)` helper touches two production files (dispatcher plus orchestrator), so it exceeds the one-file direct-fix budget; the migration path is recorded against the existing single-source-production-helpers item.
