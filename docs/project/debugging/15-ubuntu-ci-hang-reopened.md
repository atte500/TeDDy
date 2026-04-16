# Bug: Ubuntu CI Test Suite Hang (Reopened)

- **Status:** Unresolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- Pytest suite still hangs on Ubuntu CI workers at ~24% progress (approx. 144 tests).
- The hang was previously believed to be resolved by adding `PYTEST_CURRENT_TEST` TTY restoration guards.
- **MRE:** Trigger CI via remote protocol with diagnostic output.

## Diagnostic Analysis

### Causal Model
- `pytest` captures `stdout` and `stderr` using OS-level pipes during test execution.
- If a test indirectly spawns a background process via `subprocess.Popen` (e.g., `spawn_editor` for TUI previews, or `ShellAdapter` executing a background action) without explicitly redirecting `stdin`, `stdout`, and `stderr` to `subprocess.DEVNULL`, the child process inherits Pytest's capture file descriptors.
- If the child process outlives the test (e.g., a headless editor waiting for input), Pytest's teardown mechanism hangs infinitely waiting for an EOF on the capture pipe. This blocks the main thread from completing test setup/teardown, resulting in the non-deterministic `[ 24%]` deadlock on Ubuntu CI workers.
- **Verified Discovered Leaks:**
  1. `ReviewerApp` thread leaks in unit tests.
  2. `subprocess.Popen` file descriptor leaks in `spawn_editor` (helpers) and `diff_viewer` (previews) where `stdout/stderr/stdin` were not routed to `DEVNULL`.
  3. `test_execute_timeout_does_not_reset_terminal` mocked `subprocess.Popen` but left `process.pid` as a `MagicMock`. `MagicMock` natively casts to `1` when passed to C-extensions like `os.killpg`. This caused `os.killpg(1, signal.SIGKILL)` on Ubuntu CI workers, instantly terminating the test runner's container/process-group and causing an abrupt job hang.

### Discrepancies
- The previous TTY guard fix did not resolve the hang.
- [2026-04-16] Wiring regression: `IPlanReviewer` resolved to `ConsolePlanReviewer` in tests. (resolved: Aggressive `PYTEST_CURRENT_TEST` guard in `reviewer.py` removed, but then reinstated and dynamically patched via `monkeypatch.delenv` to safely bypass).
- `ShellAdapter` uses `preexec_fn` which causes deadlocks. (resolved: Checked `src/teddy_executor/adapters/outbound/shell_adapter.py`. It uses `start_new_session=True`, NOT `preexec_fn`.)
- [2026-04-16] Since the hang occurs even with `xdist` disabled (`-n 0`), it is likely caused by a leaked background thread or `asyncio`/`anyio` event loop from a previous test. (resolved: It is not a thread leak, but an OS-level file descriptor leak. `subprocess.Popen` in `spawn_editor` and `ShellAdapter` inherits Pytest's capture pipes. Background processes keep these pipes open, deadlocking Pytest's teardown loop waiting for EOF).

### Investigation History
- [2026-04-16] **RED STATE RESET:** Attempted to fix the hang by replacing naked Textual `ReviewerApp` instances with `MagicMock` in unit tests, suspecting an `anyio` thread leak. Pushed to remote CI, but the suite still deadlocked at exactly the same spot (~24% progress).
- [2026-04-16] Re-analyzed the architecture and Pytest mechanics. Discovered that `spawn_editor` in `textual_plan_reviewer_helpers.py` and background execution in `shell_adapter.py` use `subprocess.Popen` without explicitly routing standard I/O to `DEVNULL`.
- [2026-04-16] Identified the verifiable root cause: Pytest's output capture mechanism deadlocks infinitely waiting for an EOF from background child processes that inherited its stdout/stderr pipes.
- [2026-04-16] Case reopened. Issue persists in CI environment. Preparing Remote CLI Protocol.
- [2026-04-16] Attempted remote monitoring via `gh run view`. Encountered `null` job IDs during early workflow initialization. Resetting and retrying with robust polling.
- [2026-04-16] Identified `preexec_fn` in `ShellAdapter` as the likely cause of Ubuntu deadlock due to `fork()` semantics in `pytest-xdist`.
- [2026-04-16] Identified Windows worker crash in `WebScraperAdapter` tests, likely due to `trafilatura`/`lxml` binary instability in parallel tests.
- [2026-04-16] **RED STATE RESET:** Discovered that a planned `EDIT` to remove `preexec_fn` from `ShellAdapter` was skipped due to a prior validation failure. The `preexec_fn` remains active in the codebase.
- [2026-04-16] **Correction:** Read `shell_adapter.py`. It does NOT contain `preexec_fn`. It uses `start_new_session=True`. The previous RED STATE diagnosis was based on a false premise. The root cause of the Ubuntu hang is unknown.
- [2026-04-16] **RED STATE RESET:** Attempted to use a Remote CLI watchdog script on temporary branches to catch the hanging test in CI. The workflow runs were too slow, and the logs were inaccessible while running. The approach created excessive branch clutter and was manually aborted.
- [2026-04-16] Executed strict Remote Probing Protocol (Rule 14). Ran `pytest -n 0 -vv -s --setup-show` on transient branches to isolate the hang.
- [2026-04-16] Discovered the hang is **highly non-deterministic**. It randomly strikes during the setup phase of different tests (e.g., hanging at `SETUP F env` for `test_regression_read_action_suspend`, and later at `SETUP F container` for `test_confirm_action_handles_eof_error`).
- [2026-04-16] Since the hang occurs even with `xdist` disabled (`-n 0`), it is likely caused by a leaked background thread or `asyncio`/`anyio` event loop from a previous test (suspected: Textual `App` instances leaving unresolved worker threads) deadlocking Pytest's fixture teardown/setup on Ubuntu workers. (resolved: False diagnosis on which tests were responsible. The actual leaked instantiations were found in `test_tui_ux_regressions.py`, `test_reviewer_app_bindings.py`, and `test_tui_view_plan.py`. These tests instantiate `ReviewerApp` to check static class attributes but fail to call `app.run_test()`, leaking `anyio` threads that hold open file descriptors and deadlock Pytest's teardown loop).
- **Current Workspace State:** Workspace hard-reset to `main`. All `debug/*` branches deleted.
