# Bug: The quit-key interrupt notice is suppressed on Windows
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc bug)
- **Vertical Slice:** N/A (ad-hoc bug)
- **Specs:** N/A

## Symptoms
Pressing the bare `q` key during an interactive TeDDy session on Windows terminates the process immediately. The expected one-line notice `Interrupted by user (q). To continue the session, use `teddy resume`.` is never printed, and the turn report is not written.

Minimal reproduction: open a TeDDy session in a Windows console, press `q`, and observe that the process exits with code 2 and prints nothing.

## Context & Scope
### Regressing Delta
The bare-`q` interrupt feature introduced the self-delivery chain. Commit `2575af1b` (`feat(session-notices): name the pressed key in the interrupt notice`) added `_record_quit_source` in `src/teddy_executor/container.py`, which records the key and then calls `os.kill(os.getpid(), signal.SIGINT)`. The listener fallback in `src/teddy_executor/adapters/outbound/terminal_quit_key_listener.py::_trigger` uses the same call. The Windows path was never exercised.

### Environmental Triggers
- Windows (`sys.platform == "win32"`).
- A real console attached to stdin (`sys.stdin.isatty()` is true), so the listener starts.
- A bare `q` press processed by `msvcrt.kbhit()` and `msvcrt.getwch()`.

### Ruled Out
- Notice composition: `format_interrupt_notice` is pure and platform-neutral.
- The TTY gate: the Windows console reports stdin as a TTY, so the listener starts.
- Guard phase semantics: the guard flag stays clear because the handler never runs.
- Source recording: `record_source("q")` runs before the self-delivery call.
- Windows console output state: the replica printed the notice under the same console conditions, so the terminal state does not suppress the message.
- The reader thread: the threaded replica reached the handler and printed the notice, so delivery from a worker thread is not the defect.

## Diagnostic Analysis
### Causal Model
1. `TerminalQuitKeyListener.start()` spawns the reader thread. On Windows the reader polls `msvcrt.kbhit()` and consumes the key with `msvcrt.getwch()`.
2. The reader maps `q` (0x71) to `_trigger()`, which invokes the Constructor-Injected `on_quit` callback.
3. The composition root binds `on_quit` to `_record_quit_source`, which records `"q"` on the shared `InterruptGuard` and then calls `os.kill(os.getpid(), signal.SIGINT)`.
4. On Windows, `os.kill` calls `TerminateProcess` for every signal value except `CTRL_C_EVENT` and `CTRL_BREAK_EVENT`.
5. The process dies with exit code 2 before the Python-level SIGINT handler runs. The `interrupted` event stays clear, so neither notice emission site in `session_cli_handlers.py` executes.

### Discrepancies
- [x] Expected: pressing `q` prints the interrupt notice and preserves the report. Observed: the Windows process terminates silently with exit code 2. (Resolved: `os.kill` maps every Windows signal except `CTRL_C_EVENT` and `CTRL_BREAK_EVENT` to `TerminateProcess`, so the process dies before the Python handler runs.)
- [x] Expected: the self-delivery drives the shared `InterruptGuard`. Observed: the delivery mechanism bypasses the Python handler on Windows. (Resolved: `signal.raise_signal` reaches the guard handler from the main thread and from the reader thread.)

### Investigation History
1. Located the notice emit sites in `session_cli_handlers.py` and the `INTERRUPT_REASON` constant. Observed that both sites depend on the guard handler running.
2. Read the listener, guard, terminal helper, and notice formatter. Observed an unconditional `os.kill(os.getpid(), signal.SIGINT)` in two self-delivery sites.
3. Inspected commits `2575af1b` and `7ab15ccf`. Observed the self-delivery wiring and the POSIX-only ISIG work, with no Windows delivery path.
4. Checked the CPython 3.14 documentation and source. Observed that `os.kill` falls back to `TerminateProcess` on Windows for SIGINT, while `signal.raise_signal` uses the CRT `raise()` path that reaches the Python handler.
5. Ran the MRE locally on Darwin as a POSIX control. All four scenarios (production and replica delivery, direct and threaded) printed the notice with exit code 0. This proves the harness isolates only the SIGINT delivery primitive and that the replica primitive reaches the guard handler from a worker thread.
6. Aligned the debug workflow artifact name with the download name used by `make probe`, so the remote Windows result can be retrieved.
7. Ran the Remote Windows Probe (run `39247429235`) on `windows-latest` with Python 3.14.8. Both production scenarios exited with code 2 and produced no output. Both replica scenarios printed the `Interrupted by user (q)` notice with exit code 0, including the threaded variant. This proves the Windows `os.kill` termination semantics and the `signal.raise_signal` repair empirically.
8. Audited the consumers. The production self-delivery appears in `container._record_quit_source` and in `TerminalQuitKeyListener._trigger`. Three test modules pin the delivery seam. The repair spans more than one production file, so it is handed to the Developer after Alignment.

## Solution
### Root Cause
Verified with the sandbox replica and the Remote Windows Probe (run `39247429235`). On Windows, `os.kill(pid, sig)` calls `TerminateProcess` for every signal except `CTRL_C_EVENT` and `CTRL_BREAK_EVENT`. Both self-delivery sites therefore kill the process with exit code 2 before the installed `InterruptGuard` handler runs. The `interrupted` flag stays clear, so neither notice emission site in `session_cli_handlers.py` executes. Replacing the delivery primitive with `signal.raise_signal(signal.SIGINT)` routes the signal through the process-level CRT handler and reaches `InterruptGuard._handle_signal` from the main thread and from the reader thread. The boundary then prints the notice and the orchestrator writes the report. The production path stayed silent with exit code 2 while the replica printed the notice with exit code 0 in both scenarios.

### Affected Components
- `src/teddy_executor/container.py::_record_quit_source`: replace `os.kill(os.getpid(), signal.SIGINT)` with the shared cross-platform delivery.
- `src/teddy_executor/adapters/outbound/terminal_quit_key_listener.py::_trigger`: same replacement in the default no-hook branch.
- `src/teddy_executor/core/utils/interrupt_guard.py`: proposed home for a module-level `raise_interrupt()` helper. The delivery primitive then lives beside the guard contract that consumes it, and both call sites stay in lockstep.
- `tests/suites/integration/core/services/test_quit_source_wiring.py`: monkeypatches `os.kill`. It must observe the shared helper instead.
- `tests/suites/unit/adapters/outbound/test_terminal_quit_key_listener_reader.py`: `test_read_loop_self_delivers_sigint_on_quit_key` and `test_trigger_invokes_injected_on_quit_instead_of_self_delivering` pin the `os.kill` tuple. Both must observe the shared helper.
- `tests/suites/unit/core/utils/test_interrupt_guard.py`: `TestRealSignalDelivery` uses `os.kill` and is skipped on Windows. Switching to `raise_signal` restores Windows coverage of real delivery.
- Migration path: add the helper and its unit test, then move the two production call sites, then update the three test seams. No port signature and no data contract changes, so the steps are non-breaking and can land as one slice.

### Verification
- Remote Windows Probe run `39247429235`: production `rc=2` and silent, replica `rc=0` with the notice, in direct and threaded modes.
- Local Darwin POSIX control: four green scenarios.
- Preserved MRE: [01-quit-notice-mre.py](/spikes/debug/windows-quit-notice-suppression/01-quit-notice-mre.py)
- Preserved replica: [replica_interrupt_guard.py](/spikes/debug/windows-quit-notice-suppression/replica_interrupt_guard.py)
