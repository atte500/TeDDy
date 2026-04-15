# Bug: Terminal State Corruption on EXECUTE Timeout
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When an `EXECUTE` action fails due to a timeout, the parent terminal is left in a corrupted "raw" state. This manifests as visible escape sequences (like `;90;9M...`) appearing when the mouse is moved or clicked, indicating that mouse tracking was not cleanly disabled by the TUI or the child process.

**MRE:** `python debug/repro_final.py`

## System Model
### Causal Model
1. **Terminal Corruption on Timeout:** When TeDDy executes a command that times out, it must kill the process. `subprocess.run` defaults to `SIGTERM` on the immediate process ID. Grandchildren (like the Textual TUI) are orphaned, remain connected to `/dev/tty`, and leak escape sequences that visibly corrupt terminal mouse tracking.
2. **The `os.setpgrp` Regression:** To fix the corruption, `ShellAdapter` was modified to use `subprocess.Popen(preexec_fn=os.setpgrp)` and `os.killpg()`. This successfully guarantees process tree destruction. However, it introduced a severe regression: commands like `pytest` now hang indefinitely.
3. **The `SIGTTIN` Suspension:** The hang is not a leaked pipe. When `os.setpgrp` is used, the child process is placed in a new "background" process group. However, it still inherits `stdin` from the TeDDy CLI. When `pytest` (or a dependency like `rich`) attempts to query the terminal size via `stdin`, the OS kernel detects a background process interacting with the controlling terminal and instantly sends a `SIGTTIN` (Terminal Input) signal. This signal does not kill the process; it *suspends* it indefinitely. Because the process is suspended, it never exits, and TeDDy blocks forever waiting for EOF on `process.communicate()`.

### Discrepancies
- None. The root cause is fully understood. We must apply `signal.SIG_IGN` to `SIGTTIN` and `SIGTTOU` within the `preexec_fn` to prevent the OS from suspending the background process group.

### Investigation History
- **Initial Attempt:** Used `start_new_session=True` to enable process group termination. *Result:* Stripped the controlling terminal, breaking the Textual TUI completely.
- **Second Attempt:** Used `preexec_fn=os.setpgrp` to isolate the process group while keeping the session. Replaced `SIGTERM` with `SIGKILL` to guarantee process destruction. *Result:* Successfully cured the terminal corruption bug.
- **Third Attempt:** Implemented a direct-to-`/dev/tty` hard reset sequence to guarantee a clean terminal even if the TUI died abruptly. *Result:* Mangled the `pytest` output because tests intentionally simulate timeouts, sending the alt-screen exit sequence (`\x1b[?1049l`) during the progress bar rendering. Fixed by wrapping the restore sequence with a `PYTEST_CURRENT_TEST` guard.
- **Current State:** The core terminal corruption bug is verified resolved manually. However, programmatic test execution via TeDDy hangs due to a leaked pipe.

**2026-04-15: Context Reset (Red State)**
- **Attempt:** Created a diagnostic probe (`probe_pytest_hang.py`) to catch the leaky background process by wrapping `pytest` with a 25-second `communicate()` timeout.
- **Failure:** The probe itself triggered a hard 60-second shell timeout. In the `TimeoutExpired` exception block, the probe called `process.kill()` (killing only the main `pytest` process) and then unconditionally called `stdout, stderr = process.communicate()`. Because the leaked grandchild was still alive and holding the inherited pipe open, this fallback `communicate()` blocked indefinitely. This definitively proves we are dealing with an orphaned, long-running child process holding `stdout`.
- **Current Workspace State:**
  - `src/teddy_executor/adapters/outbound/shell_adapter.py` is partially modified and uses `os.setpgrp` with `Popen`.
  - `tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py` is broken because it explicitly mocks `subprocess.run` instead of `Popen`.
  - The pipe-leak in the test suite itself is still unidentified.

**2026-04-15: Context Reset 2 (Red State)**
- **Attempt:** Ran extensive diagnostics to identify the pipe hostage. Discovered that running `pytest -s -v` (no pipes) natively finishes perfectly in 9 seconds. However, running `pytest` piped inside TeDDy, or via `subprocess.Popen(stdout=PIPE)`, always hangs indefinitely.
- **Failure:** An `lsof` probe timed out at 60s because the TeDDy CLI executor killed the diagnostic wrapper before it could parse the massive file descriptor list on macOS.
- **Current Workspace State:**
  - The theory is solid: an acceptance test is spawning a grandchild process (e.g., `bash` or `python -c`) that inherits the pipe and never closes it.
  - Need to test execution of smaller test subsets (e.g., `pytest tests/suites/acceptance/`) to isolate the specific file causing the leak without running the entire suite.

## Solution
### Implemented Fixes
- Modified `src/teddy_executor/adapters/outbound/shell_adapter.py` to correctly kill process groups using `subprocess.Popen(preexec_fn=...)` and `os.killpg(..., signal.SIGKILL)`. This prevents grandchild processes (like Textual TUIs) from being orphaned and corrupting the terminal mouse tracking state.
- Crucially, applied `signal.signal(signal.SIGTTOU, signal.SIG_IGN)` and `signal.signal(signal.SIGTTIN, signal.SIG_IGN)` inside the `preexec_fn` immediately after `os.setpgrp()`. This prevents the OS from suspending the background process group when a command like `pytest` or `rich` attempts to query the terminal size from the inherited `stdin`.
- Removed unnecessary process pipe-closing fallbacks, replacing them with a simple 0.5s grace period for the OS to naturally flush buffers after `SIGKILL`.
- Updated unit tests in `tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py` to correctly mock and assert against `subprocess.Popen.communicate` instead of `subprocess.run`.

### Prevention
- The regression suite (`test_shell_adapter_timeout.py`) has been aligned to strictly assert the new `Popen` and `communicate` logic, verifying that timeouts trigger terminal restoration and the appropriate return codes.
- **Robust Integration Test:** Added `test_posix_sigttin_suspension_prevention` to `test_shell_adapter.py`. Because shell wrappers (`bash -c`) can sometimes mask signal handlers from introspection, the test uses a deterministic behavioral approach: it executes a child process that queries `sys.stdin.isatty()`. In a background process group, this query actively triggers a `SIGTTIN` from the OS kernel. By asserting that the command evaluates successfully and exits without hanging, we deterministically prove that `ShellAdapter` successfully applied `SIG_IGN` to prevent suspension.
