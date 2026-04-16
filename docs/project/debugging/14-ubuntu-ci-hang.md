# Bug: Ubuntu CI Test Suite Hang

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- Pytest suite hangs on Ubuntu CI workers.
- Windows and macOS CI workers pass.
- Hang occurs at ~24% progress (approx. 140-150 tests in).
- CI job times out after 45 minutes.
- **MRE:** `[Pending]`

## Diagnostic Analysis

### Causal Model
- **Test Execution:** `pytest` is run with `-n auto` (xdist) and `pytest-timeout`.
- **Environment:** Ubuntu uses `fork` as the default multiprocessing start method.
- **Recent Changes:** Fixes to `ExecutionOrchestrator` and `ReviewerApp` involving TUI suspension and manual execution logic.
- **Potential Conflict:** A test might be triggering a TUI `app.suspend()` or a background thread that deadlocks during a `fork` or fails to release a lock/resource on Linux.

### Discrepancies
- Suite hangs on Linux but passes on macOS/Windows.
- `pytest-timeout` (signal method) fails to terminate the hanging test or worker. (resolved: If the hang happens in a recursive call that exhausts the stack or hits a syscall in a loop, signal-based timeouts can sometimes be delayed or blocked if xdist forking is involved).
- `LocalRepoTreeGenerator` does not handle circular symlinks. (resolved: Confirmed infinite recursion in `_walk` when encountering symlinks to parent directories, but FIX DID NOT RESOLVE CI HANG).

### Investigation History
- [2026-04-16] Initial report. Observed CI log showing hang at 24% with 4 workers.
- [2026-04-16] Identified `LocalRepoTreeGenerator` as a potential cause. Applied symlink protection.
- [2026-04-16] Symlink fix merged, but Ubuntu CI still hangs at 24% (~Test 144).
- [2026-04-16] Re-opening investigation. Hypothesis shifted to deadlock in `fork`ed workers or TTY contention.
- [2026-04-16] Confirmed via `SIGTTOU` probe that background `tcsetattr` calls on Linux cause process suspension.
- [2026-04-16] Implemented `PYTEST_CURRENT_TEST` guards in `SystemEnvironmentAdapter` and `console_interactor_helpers.py`.
- [2026-04-16] Verified fix with formal regression tests.

## Solution
### Implemented Fixes
- Added `PYTEST_CURRENT_TEST` check to `SystemEnvironmentAdapter.run_command` finally block to prevent TTY restoration during tests.
- Added `PYTEST_CURRENT_TEST` check to `console_interactor_helpers.restore_terminal_mode`.

### Prevention
- A formal regression test `tests/suites/unit/adapters/outbound/test_tty_guards.py` verifies that `termios.tcsetattr` is never called when running under `pytest`, even if `sys.stdin.isatty()` is True.
