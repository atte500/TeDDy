# Bug: EXECUTE Timeout Output Not Truncated
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [ShellAdapter design](/docs/architecture/adapters/outbound/shell_adapter.md)

## Symptoms
Expected: when an `EXECUTE` action times out, its captured partial `stdout` is capped to the effective `max_lines` (default from `execute.max_output_lines`, 100; per-call override wins) and carries the standard tail-truncation hint.

Actual: a timed-out command returns its full partial `stdout` prefixed with the timeout warning, with no truncation hint and no respect for the line cap. A slow command that emitted hundreds of lines before the timeout floods the report.

Minimal reproduction: call `ShellAdapter.execute(command, timeout=...)` against a command whose partial output exceeds `max_execute_lines` and which raises `subprocess.TimeoutExpired` during the wait. The returned `stdout` is far longer than the cap.

## Context & Scope
### Regressing Delta
Structural, not line-local: truncation lives on the shared post-processing path `_process_execution_results` (`src/teddy_executor/adapters/outbound/shell_adapter.py`), reached by the normal and interrupt paths. The timeout path is an early `return self._handle_timeout(process, timeout or 0)` (caller near line 424) and `_handle_timeout` (line 180) builds its own `ShellOutput` dict, never calling `truncate_lines` and never receiving `max_lines`. Git history of `_handle_timeout` (commits `b0a18211`, `4b399cad`) shows it has never truncated output; the capping was only ever applied on the shared processing path, so the timeout return point was simply never updated to honor the cap.

### Environmental Triggers
Any command that exceeds `timeout` while its combined output exceeds `max_execute_lines`, on POSIX or Windows. No special environment is required; the MRE mocks the subprocess boundary to keep the reproduction deterministic and fast.

### Ruled Out
- Interrupt path: It returns through `_process_execution_results`, so truncation is applied. Not affected.
- Downstream report formatter: Out of scope; the adapter owns the line cap per its documented contract ("`stdout` is truncated at the tail to the effective line cap").

## Diagnostic Analysis
### Causal Model
`execute` -> `_run_subprocess` -> `_await_process(process, timeout)` raises `subprocess.TimeoutExpired`. `_run_subprocess` catches it and returns `self._handle_timeout(process, timeout or 0)`. `_handle_timeout` kills the process group, gathers partial output via `communicate(timeout=0.5)`, builds `stdout = warning + sanitized(output)`, and returns a `ShellOutput` with the timeout exit code `124` — bypassing `truncate_lines` entirely and with no access to the per-call `max_lines`. The normal path instead falls through to `_process_execution_results`, which sanitizes and calls `truncate_lines(sanitized_stdout, max_lines=effective_max_lines, direction="tail", action_type="execute")`.

### Discrepancies
- [x] Timeout `stdout` is not capped to the effective `max_lines` and carries no truncation hint. (Resolved: `_handle_timeout` now tail-truncates the decoded body to the effective `max_lines` before prefixing the timeout warning.)
- [x] Does the interrupt path share the gap? No — it re-enters `_process_execution_results`, which truncates. (Resolved: interrupt flag is attached after processing.)
- [x] `_handle_timeout` cannot honor a per-call `max_lines` override. (Resolved: its signature omits `max_lines`; the caller passes only `(process, timeout or 0)`.)

### Investigation History
1. Located the truncation boundary: `git grep` + read showed `_process_execution_results` calls `truncate_lines`, while `_handle_timeout` assembles its own dict. Conclusion: timeout is a separate return point that bypasses the cap.
2. Read `truncate_lines` (tail direction, `action_type="execute"` dynamic hint) and config schema (`execute.max_output_lines` default 100, minimum 1). Conclusion: the cap is a tail slice with a dynamic hint, and per-call override must be threaded through.
3. Traced the interrupt path: it flows through `_process_execution_results` with the flag attached afterward. Conclusion: only the timeout path is defective.
4. `git log` on `_handle_timeout` (commits `b0a18211`, `4b399cad`) and on `truncate_lines` showed no historical timeout truncation. Conclusion: the copy in `_handle_timeout` intentionally assembled its own output, leaving the tail-truncation contract unfulfilled.
5. `git grep` across the timeout and integration test files returned no truncation assertions. Conclusion: the bug is uncovered; a regression test is required with the fix.
6. Wrote `spikes/debug/shell-timeout-output-truncation/01-shell-timeout-output-truncation-mre.py` driving the real `ShellAdapter` into a mocked timeout with 200 lines of partial output against a cap of 5. Observed `return_code=124`, `stdout_lines=201`, "BUG REPRODUCED". Conclusion: the defect is empirically reproduced.
7. Built a fixed replica (`replica_shell_adapter.py`), applied tail truncation in `_handle_timeout`, and threaded `max_lines` from `_run_subprocess`; ran `02-shell-timeout-output-truncation-verify.py`. Observed capped bodies (7 lines at the default cap, 5 lines under a 3-line override) with warning and hint present, and the warning-only body for empty output. Conclusion: the fix design is verified in isolation.
8. Applied the identical fix to `src/teddy_executor/adapters/outbound/shell_adapter.py` and appended two regression tests to `test_shell_adapter_timeout.py`. The original MRE flipped to `stdout_lines=7`, "OK: timeout output truncated", and `make test` passed (2158 passed, 5 skipped). Conclusion: root cause confirmed and fixed directly in production.

## Solution
### Root Cause
Verified and fixed directly in production (`src/teddy_executor/adapters/outbound/shell_adapter.py`). `_handle_timeout` was a separate early-return path that assembled its own `ShellOutput` without ever calling `truncate_lines` and without access to the per-call `max_lines`, so a timed-out command's partial stdout bypassed the tail cap. The fix threads `max_lines` from `_run_subprocess` into `_handle_timeout` and tail-truncates the decoded command body to the effective cap (per-call override, else `max_execute_lines`) via the same `truncate_lines(..., direction="tail", action_type="execute")` used by `_process_execution_results`, then prefixes the timeout warning. Empty output still returns the warning alone.

### Affected Components
- `ShellAdapter._handle_timeout`: Added an optional `max_lines` parameter and tail truncation of the decoded command body, preserving the warning-only result for empty output. Applied to `src/`.
- `ShellAdapter._run_subprocess`: Passes `max_lines` into `_handle_timeout` at the `TimeoutExpired` call site. Applied to `src/`.
- `tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py`: Added `test_execute_timeout_truncates_partial_output_to_default_cap` and `test_execute_timeout_truncates_partial_output_with_max_lines_override`.
- `docs/architecture/adapters/outbound/shell_adapter.md`: Component design note updated to state that the timeout path applies the tail cap.

### Proof Artifacts
- MRE: [01-shell-timeout-output-truncation-mre.py](/spikes/debug/shell-timeout-output-truncation/01-shell-timeout-output-truncation-mre.py)
- Replica: [replica_shell_adapter.py](/spikes/debug/shell-timeout-output-truncation/replica_shell_adapter.py)
- Replica verification: [02-shell-timeout-output-truncation-verify.py](/spikes/debug/shell-timeout-output-truncation/02-shell-timeout-output-truncation-verify.py)
