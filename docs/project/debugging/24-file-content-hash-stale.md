# Bug: File Content Hash Not Refreshed After EDIT – Stale Hash Leads to Validation Failure and Missing Logging
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- **Expected:** After a successful `EDIT` action on a file, subsequent `EDIT` actions on the same file should use the updated file content for hash comparison. Validation failures due to hash mismatch should be logged to the user's terminal.
- **Actual:** The file content hash is not refreshed after an `EDIT` action, causing the next `EDIT` on the same file to throw "File content modified during execution". Additionally, when this validation error occurs, no error is printed to the user; the failure is silent.
- **Reproduction Steps:**
  1. Execute a plan with two `EDIT` actions targeting the same file sequentially.
  2. The first `EDIT` succeeds and modifies the file content.
  3. The second `EDIT` uses a `FIND` block that matches the **original** content (before the first edit) but the system's hash still points to the old content; the edit fails with "File content modified during execution".
  4. The user sees no error message in the console/log.

## Context & Scope
### Regressing Delta
No regressing commit identified — the `_file_hashes` pre-check mechanism was added as a feature for mid-execution consistency within a single plan execution, but was NEVER designed to handle cross-turn persistence. The hash is stored in `ActionExecutor._file_hashes` (an instance variable) and persists across turns because `ActionExecutor` is registered as a singleton in the DI container. The oversight: no refresh/recomputation of hashes at the START of plan execution or at the START of `confirm_and_dispatch`.

### Environmental Triggers
- **Primary trigger:** User manually modifies a file between turns. The stale hash from the previous turn's EDIT triggers a false "File content modified during execution" failure.
- **Secondary trigger:** Cross-turn EDIT actions on the same file where the file was externally modified. The hash persists from the last successful EDIT and is not refreshed at plan start.

### Ruled Out
- Within-plan sequential EDIT actions: Confirmed working correctly because hash IS updated post-dispatch (confirmed in `action_executor.py` line ~319).
- `EXECUTE` actions: Confirmed clearing the hash map entirely (line ~323).
- File system race conditions: The pre-check is deterministic based on stored hash vs. current file content.
- Plan parser/validator: The bug is purely in the ActionExecutor's hash management.

## Diagnostic Analysis
### Causal Model
The `ActionExecutor._file_hashes` dictionary stores SHA-256 hashes of file content after successful EDIT actions. This hash is used for a mid-execution consistency check: before executing any EDIT action, the current file hash is compared against the stored hash. If they differ, the action fails with "File content modified during execution".

The flaw: `_file_hashes` is NEVER cleared or refreshed at the start of plan execution. It is an instance variable that persists across turns because `ActionExecutor` is a singleton-scoped dependency in the `punq` DI container. When a user manually modifies a file between turns (or the file changes for any other reason), the stored hash from the previous turn's EDIT becomes stale, causing the pre-check to falsely trigger.

Additionally, when the pre-check fails, the early-returned FAILURE ActionLog bypasses the normal `dispatch_and_execute` path. The failure is assembled into the execution report but currently is not logged to the terminal during execution — the user only sees the aggregated report after all actions complete.

### Discrepancies
1. The pre-check fires when file hasn't changed concurrently — hash mismatch is caused by stale hash from previous turn, not concurrent modification. (Resolved: The hash IS updated post-dispatch within a plan, but NOT refreshed at plan start across turns. Confirmed by MRE and code reading.)
2. The failure ActionLog should be logged to terminal during execution — currently the user sees no error message until the final aggregated report. (Resolved: The pre-check failure returns early from `confirm_and_dispatch` as a FAILURE ActionLog, which flows through the orchestrator into the aggregated `ExecutionReport`. The report is displayed to terminal via `handle_report_output` in `cli_helpers.py` which calls `typer.echo()` post-hoc — meaning the user only sees the failure in the aggregated output, not as a real-time log during execution. The fix adds `logger.error()` in the pre-check failure path to provide immediate terminal feedback.)

### Investigation History

## Solution
### Root Cause
The `ActionExecutor._file_hashes` dictionary stores SHA-256 hashes of file content after successful EDIT actions for a mid-execution consistency check. The bug: these hashes were NEVER refreshed at the start of plan execution (i.e., at the beginning of `confirm_and_dispatch`). Because the same `ActionExecutor` instance is reused across turns within a session (resolved once via `OrchestratorPorts`, effectively a de facto singleton), the hash persisted from the previous turn. When a user manually modified a file between turns, the stale hash caused the pre-check to falsely trigger "File content modified during execution".

### Fix Applied (2 changes to `action_executor.py`):
1. **Hash refresh at start:** Added a block at the beginning of `confirm_and_dispatch` (before the pre-check) that recomputes the hash from current disk state and updates `_file_hashes[path]`. This ensures cross-turn staleness is resolved while preserving genuine concurrent modification detection (file modified between refresh and actual dispatch).
2. **Real-time logging:** Added `logger.error()` in the pre-check failure path to provide immediate terminal feedback when the check does fail, rather than relying solely on the post-hoc aggregated report.

### Preventative Measures (Systemic)
- **Categorical root cause:** Singleton-like state persistence across plan executions. While `ActionExecutor` is registered as `transient` in the container, it is resolved once per session because `OrchestratorPorts` (which holds the `ActionExecutor`) is resolved once when the `ExecutionOrchestrator` is created. This creates a de facto singleton scope.
- **Recommendation:** Review the DI resolution pattern for `OrchestratorPorts`/`ExecutionOrchestrator` to ensure that stateful services like `ActionExecutor` are either freshly resolved per turn or explicitly reset at the start of each plan execution. Consider making `ActionExecutor`'s hash map a parameter that is cleared externally by the orchestrator.
- **No other instances found:** The systemic audit (`git grep` for `Scope.singleton` and mutable state patterns) found no other services with similar cross-turn state persistence issues in the codebase.
1. **Hypothesis:** Hash not refreshed after EDIT. **Observation:** Code reading of `action_executor.py` shows hash IS updated post-dispatch (line ~319). **Conclusion:** Within-plan scenario is fine; the bug is cross-turn.
2. **Hypothesis:** Hash not refreshed at plan start. **Observation:** No code path resets `_file_hashes` at the beginning of a plan execution. The orchestrator's `execute()` method calls `_process_plan_actions()` without any hash reset. **Conclusion:** Confirmed — hash persists across turns because `ActionExecutor` is a singleton.
3. **Hypothesis:** MRE confirms the stale hash failure. **Observation:** MRE output shows "✓ BUG CONFIRMED: Hash mismatch detected due to stale hash!" with exact hash comparison demonstrating the mismatch. **Conclusion:** Bug is empirically confirmed.
4. **Hypothesis:** Missing terminal logging for pre-check failure. **Observation:** Pre-check returns early with a FAILURE ActionLog. This flows through the orchestrator and into the execution report. The report is rendered post-hoc by `handle_report_output` in `cli_helpers.py` — it prints the aggregated report to terminal and copies to clipboard. No real-time per-action logging exists for the pre-check path. The early return bypasses `dispatch_and_execute`, which would have logged execution details. **Conclusion:** Confirmed — the fix must add explicit logging in the pre-check failure path (done in shadow file via `logger.error()`).
5. **Hypothesis:** Shadow fix works. **Observation:** Verification MRE confirms: "ALL TESTS PASSED ✓" — cross-turn staleness resolved (hash refreshed at start), genuine concurrent modification still detected. **Conclusion:** Fix strategy is empirically proven.
