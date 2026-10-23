# Bug: Windows Quit-Key Unreliability and Editor-Open Latency
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc regression)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
On Windows 11, pressing `q` during a session sometimes produces no interrupt at all, so the user must press it again. On macOS the same key interrupts instantly and reliably. Opening the external editor from the TUI takes about one second on Windows, while macOS opens it instantly. Both symptoms persist after earlier fix attempts.

## Context & Scope
### Regressing Delta
The Windows quit regression is the `run_interruptible` design shipped with the quit-key slice in `docs/project/debugging/71-quit-key-interrupt-latency.md` (commits `e71ccb02`, `e719badf`, `b1d6e288`), which waits in a single blocking `Future.result()` on the main thread. The editor launch path was last changed by the `editor-normalization` commits (`42b10211` through `b069fbfb`) and carries no TeDDy code cause.

### Environmental Triggers
Windows 11 console with an interactive TTY session. macOS is the control platform and must keep its current instant behavior.

### Ruled Out
- The quit listener does not race Textual for the console input buffer. `textual_plan_reviewer.py` wraps the whole `app.run()` in `stdin_owned()`, so the listener backs off while Textual owns the keyboard.
- The stdin-ownership counter cannot leak a permanent backoff. `stdin_ownership.py` is a reference-counted depth counter released in a `finally` block.
- Action subprocesses cannot consume console keystrokes. `shell_adapter.py` and the synchronous `SystemEnvironmentAdapter.run_command` pass `stdin=subprocess.DEVNULL`, and background launches use `CREATE_NO_WINDOW` on Windows.
- The listener poll interval (`_POLL_INTERVAL = 0.05` seconds) cannot explain a missed key.
- The Windows listener never changes the console mode. `_enter_noncanonical_mode` returns early on `win32`, so `_read_one_byte_windows` reads through `msvcrt.kbhit()` against whatever mode another reader left behind.
- The Textual shutdown does not leak a modified console input mode. `App.run_async` always awaits `App._shutdown`, which calls `driver.disable_input()` and then `driver.close()`, and `WindowsDriver.close()` runs the saved `restore()` callable.
- The editor batch launcher chain is not the source of the one-second delay. The launcher timing spike measured `codium --version` through `codium.CMD` at 0.19 seconds, while the native `VSCodium.exe --version` took 2.25 seconds, so the batch wrapper is the faster dispatch path.
- Our editor spawn does not block. The spawn-return spike measured `subprocess.Popen` returning in 0.008 to 0.017 seconds while the same commands completed in 0.298 to 3.195 seconds, so our code returns before the editor window appears.

## Diagnostic Analysis
### Causal Model
Quit key: The session quit listener polls the console and calls `raise_interrupt` when `q` is pressed. On Windows that call sets a pending CRT SIGINT flag. During the planning phase the main thread sits in `run_interruptible`'s single blocking `Future.result()`. A blocked call runs no bytecode, so the pending flag is handled only when the worker returns, which can be many seconds, and the user perceives a missed key. Polling the same future in 50 millisecond slices returns the main thread to the bytecode loop, so the handler runs within one slice. The replica proof measured 0.311 seconds against a 0.3 second fire delay and a 1.5 second worker, while the shipped blocking wait measured 1.501 seconds.

Editor: `launch_editor` and `spawn_editor` spawn the resolved launcher and return in 8 to 17 milliseconds. The editor window appears after the editor's own client-to-instance handoff on Windows, measured as a 2.5 second `launcher --status` round trip against a 0.008 second spawn return. No TeDDy code path blocks on the editor, so the delay is editor-side.

### Discrepancies
- [x] Pressing `q` on Windows sometimes produces no interrupt at all, while macOS interrupts instantly. (Resolved: the blocking `Future.result()` planning wait defers the Windows SIGINT flag until the worker returns; polling the future wakes the waiter within one 50 millisecond slice.)
- [x] Opening the editor on Windows takes about one second, while macOS opens it instantly. (Resolved: TeDDy spawns the editor in milliseconds; the delay is the editor's own Windows client-to-instance handoff, not a TeDDy code path.)
- [x] Both symptoms persist after earlier fix attempts, so the prior root causes did not cover the reported behavior. (Resolved: the earlier quit fix shipped the blocking wait, and the editor delay has no TeDDy code cause.)

### Investigation History
1. Located the prior artifacts. Case file 71 covers the POSIX interrupt latency and is resolved. Artifact 54 covered the Windows editor-open stutter and was deleted in commit `77f009ed`, so its final text must come from Git history.
2. Confirmed the shipped quit slice. `interrupt_guard.raise_interrupt` targets the main thread with `pthread_kill` on POSIX and falls back to `raise_signal` on Windows, and `interruptible_call.run_interruptible` moves the planning completion onto a daemon worker.
3. Investigated whether the listener races another console reader by reading `stdin_ownership.py` and `textual_plan_reviewer.py`; observed a reference-counted ownership counter released in `finally` and an ownership claim that spans the whole `app.run()`, which rules out a listener-versus-Textual race during review.
4. Investigated whether an action child can consume keystrokes by grepping every `subprocess` call site; observed `stdin=subprocess.DEVNULL` on the action shell and on synchronous commands, and `CREATE_NO_WINDOW` on background launches, which rules out child keystroke theft.
5. Investigated the Windows console mode by reading `terminal_quit_key_listener.py`; observed that `_enter_noncanonical_mode` returns early on `win32` and that `_read_one_byte_windows` calls `msvcrt.kbhit()` and `getwch()` against the inherited console mode, which makes the listener dependent on the mode another reader leaves behind.
6. Investigated the configured editor by reading `.teddy/config.yaml` and resolving the editor names on this host; observed `editor: codium` with no `diff_flags` override, and observed that `codium` resolves to `C:\Users\rapha\AppData\Local\Programs\VSCodium\bin\codium.cmd`, so the launch chain is a batch wrapper.
7. Investigated the Textual shutdown path by reading `App.run_async`, `App._shutdown`, and the `stop_application_mode` call-site census; observed an unconditional `await asyncio.shield(app._shutdown())`, which calls `driver.disable_input()` and then `driver.close()`, and observed that `WindowsDriver.close()` runs the saved `restore()` callable, which rules out a leaked console input mode after a normal run.
8. Investigated the editor launcher chain by running `spikes/debug/windows-quit-and-editor-latency/01-editor-launcher-timing.py` on this host; observed `codium --version` through the `.CMD` wrapper at 0.19 seconds cold and warm, and the native `VSCodium.exe --version` at 2.25 seconds cold and warm, which shows the batch wrapper runs the fast node CLI bootstrap and refutes the batch-chain latency hypothesis.
9. Investigated the editor dispatch cost and the running-instance state by running `spikes/debug/windows-quit-and-editor-latency/02-editor-dispatch-state.py`; observed a running VSCodium instance, a launcher `--status` round-trip at 2.50 seconds that exercises the instance IPC, and a launcher `--version` at 0.20 seconds, which confirms the batch dispatch is fast and shifts the editor question to our own suspend and confirm path.
10. Attempted to read the live console input and output modes; observed `GetConsoleMode` returning `ok 0` and mode `0x0` for both descriptors, because the action subshell has no attached console, so the reading is inconclusive and every console measurement must run inside a console that the probe allocates itself.
11. Investigated the SIGINT wake latency during the planning wait by running `spikes/debug/windows-quit-and-editor-latency/04-windows-sigint-wake-latency.py`; observed the shipped blocking `future.result()` interrupt at 1.501 seconds while the control polling loops interrupt at 0.301 and 0.303 seconds, which proves the Windows handler defers the pending SIGINT until the worker returns because the blocked main thread executes no bytecode.
12. Investigated whether our editor spawn blocks by running `spikes/debug/windows-quit-and-editor-latency/06-editor-spawn-return-time.py`; observed `subprocess.Popen` returning in 0.008 to 0.017 seconds against chain totals of 0.298 to 3.195 seconds for the same commands, which refutes a blocking spawn and places the remaining editor delay after our call returns.
13. Investigated whether TeDDy's editor path carries the delay by reading the `launcher --status` measurement from `spikes/debug/windows-quit-and-editor-latency/02-editor-dispatch-state.py`; observed a 2.50 second client round trip to the running instance against a 0.008 second spawn return, which attributes the editor delay to the editor's own Windows client-to-instance handoff rather than a TeDDy code path.

## Solution
### Root Cause
The Windows quit-key unreliability is a deferred-SIGINT wait. The quit listener delivers SIGINT by raising a pending CRT flag, but `run_interruptible` waited in a single blocking `Future.result()`. A blocked thread executes no bytecode, so the installed handler ran only after the worker returned and the user perceived the key as lost. The verified fix polls the worker's future in 50 millisecond slices, so the main thread returns to the bytecode loop and the handler runs within one slice. The [wake-latency MRE](/spikes/debug/windows-quit-and-editor-latency/04-windows-sigint-wake-latency.py) interrupted the shipped blocking wait at 1.501 seconds against a 0.3 second fire delay and a 1.5 second worker. The [replica proof](/spikes/debug/windows-quit-and-editor-latency/05-interruptible-call-replica-proof.py) interrupted the [polling replica](/spikes/debug/windows-quit-and-editor-latency/replica_interruptible_call.py) at 0.311 seconds. The fix was applied directly to `src/teddy_executor/core/utils/interruptible_call.py` with a regression test in `tests/suites/unit/core/utils/test_interruptible_call.py`, because the change touches one production file and its matching test file.

The editor-open latency has no TeDDy code cause. `spawn_editor` returns from `subprocess.Popen` in 8 to 17 milliseconds, and the coroutine then awaits the TUI confirmation screen instead of the editor process. The remaining delay is the editor's own Windows client-to-instance handoff, measured by the [dispatch-state probe](/spikes/debug/windows-quit-and-editor-latency/02-editor-dispatch-state.py) as a 2.5 second `launcher --status` round trip against the 0.008 second [spawn return](/spikes/debug/windows-quit-and-editor-latency/06-editor-spawn-return-time.py).

### Affected Components
- `run_interruptible` (`src/teddy_executor/core/utils/interruptible_call.py`): the wait now polls the worker's future in 50 millisecond slices. The signature and the result/exception forwarding contract are unchanged.
- `PlanningService.generate_plan` (`src/teddy_executor/core/services/planning_service.py`): the only production caller. It passes the planning phase to `run_interruptible`, so it inherits the prompt wake behaviour with no call-site change.
- `tests/suites/unit/core/utils/test_interruptible_call.py`: adds the quit-wake regression test and keeps the result, off-thread, daemon, and exception-forwarding coverage.
