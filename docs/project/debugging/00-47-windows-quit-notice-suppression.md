# Bug: The quit-key interrupt notice is suppressed on Windows
- **Status:** Unresolved
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

## Diagnostic Analysis
### Causal Model
1. `TerminalQuitKeyListener.start()` spawns the reader thread. On Windows the reader polls `msvcrt.kbhit()` and consumes the key with `msvcrt.getwch()`.
2. The reader maps `q` (0x71) to `_trigger()`, which invokes the Constructor-Injected `on_quit` callback.
3. The composition root binds `on_quit` to `_record_quit_source`, which records `"q"` on the shared `InterruptGuard` and then calls `os.kill(os.getpid(), signal.SIGINT)`.
4. On Windows, `os.kill` calls `TerminateProcess` for every signal value except `CTRL_C_EVENT` and `CTRL_BREAK_EVENT`.
5. The process dies with exit code 2 before the Python-level SIGINT handler runs. The `interrupted` event stays clear, so neither notice emission site in `session_cli_handlers.py` executes.

### Discrepancies
- [ ] Expected: pressing `q` prints the interrupt notice and preserves the report. Observed: the Windows process terminates silently with exit code 2.
- [ ] Expected: the self-delivery drives the shared `InterruptGuard`. Observed: the delivery mechanism bypasses the Python handler on Windows.

### Investigation History
1. Located the notice emit sites in `session_cli_handlers.py` and the `INTERRUPT_REASON` constant. Observed that both sites depend on the guard handler running.
2. Read the listener, guard, terminal helper, and notice formatter. Observed an unconditional `os.kill(os.getpid(), signal.SIGINT)` in two self-delivery sites.
3. Inspected commits `2575af1b` and `7ab15ccf`. Observed the self-delivery wiring and the POSIX-only ISIG work, with no Windows delivery path.
4. Checked the CPython 3.14 documentation and source. Observed that `os.kill` falls back to `TerminateProcess` on Windows for SIGINT, while `signal.raise_signal` uses the CRT `raise()` path that reaches the Python handler.
5. Ran the MRE locally on Darwin as a POSIX control. All four scenarios (production and replica delivery, direct and threaded) printed the notice with exit code 0. This proves the harness isolates only the SIGINT delivery primitive and that the replica primitive reaches the guard handler from a worker thread.
6. Aligned the debug workflow artifact name with the download name used by `make probe`, so the remote Windows result can be retrieved. Pending: run the Windows Remote Probe to confirm the production failure and the `signal.raise_signal` replica fix.

## Solution
### Root Cause
Pending sandbox verification. The candidate root cause is the Windows `os.kill` termination semantics.

### Affected Components
- `container._record_quit_source`: must deliver SIGINT through a cross-platform primitive.
- `TerminalQuitKeyListener._trigger`: same defect in the default no-hook branch.
- `InterruptGuard`: proposed home for a shared `raise_interrupt()` helper.
- Tests: `test_terminal_quit_key_listener_reader.py` and `test_quit_source_wiring.py` pin the current `os.kill` behavior and must follow the new primitive.
