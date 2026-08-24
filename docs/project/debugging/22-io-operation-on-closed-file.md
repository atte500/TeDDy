# Bug: I/O operation on closed file after Tee fix
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
After the most recent Tee fix (fileno + logging handler replacement), the system now raises "I/O operation on closed file" errors. The user reports this specifically affects Message actions. The error is a `ValueError` raised when attempting to write to a closed file descriptor (the Tee log file or a stream that was closed).

Expected: No I/O errors should affect session execution.
Actual: `ValueError: I/O operation on closed file` appears during Message actions within a session.

## Context & Scope
### Regressing Delta
The regression was likely introduced in commit `b1af9607` (the fileno fix) OR the associated logging handler replacement code added to `Tee.__enter__` in `src/teddy_executor/core/utils/io.py`. The logging handler replacement (lines 57-68) replaces ALL root logger handlers with a new `logging.StreamHandler(sys.stderr)` during Tee installation, but does NOT revert this replacement in `Tee.__exit__`.

### Environmental Triggers
- A session must be active with Tee installed.
- Something must trigger logging after the Tee's log_file has been closed (either during Tee exit or prematurely during session).
- Confirmed present on macOS Darwin.

### Ruled Out
- The original fileno AttributeError (Bug #21) is fixed and not the cause.
- Direct stdout/stderr writes via print() or typer.echo() bypass the Tee because those libraries capture file descriptors at init time.
- The error is not related to sys.stdin or stdin operations.

## Diagnostic Analysis
### Causal Model
When a session starts, `SessionLifecycleManager._handle_planning_and_execution()` installs a `Tee` before planning and execution, and tears it down afterwards. `Tee.__enter__`:
1. Replaces `sys.stdout`/`sys.stderr` with `_TeeWriter` proxies that write to both the originals and a `log_file`.
2. Saves existing root logger handlers, removes them from the root logger, and closes them.
3. Creates a new `logging.StreamHandler(sys.stderr)` where `sys.stderr` is now the `_TeeWriter` proxy, and adds it to the root logger.

`Tee.__exit__`:
1. Restores `sys.stdout`/`sys.stderr` to the originals.
2. Closes the `log_file`.
3. Does NOT restore the original root logger handlers.

After `Tee.__exit__`, the root logger still has the `StreamHandler` whose `.stream` is the old `_TeeWriter` instance. The `_TeeWriter` still holds `self._log_file` — which is now closed. Any subsequent `logger.info()` or `logging.getLogger(__name__).debug()` call triggers:
`StreamHandler.emit()` → `TeeWriter.write()` → `self._log_file.write(clean)` → `ValueError: I/O operation on closed file`.

This occurs specifically in Message actions because:
- In `PENDING_PLAN` resume state, `orchestrator.execute()` runs WITHOUT reinstalling Tee, but the handler from the previous Tee session is still active with a closed log_file.
- After any planning+execution cycle, `finalize_turn()` or other post-exit code in the session CLI handlers may log and trigger the error.

### Discrepancies
- `Initial hypothesis: Error occurs during Tee lifetime.` (Resolved: The error occurs AFTER Tee exit, not during. The Tee proxy and log_file are properly open during Tee lifetime; the bug is that the handler survives Tee exit without updating its stream reference.)

### Investigation History
1. Read Case File #21 and the current `io.py`. Noticed the root handler replacement code in `Tee.__enter__` (lines 63-72) does NOT have a revert in `Tee.__exit__` (lines 79-89). This is the prime suspect.
2. Read `session_lifecycle_manager.py`. Confirmed Tee is installed before planning+execution and torn down afterwards in `_handle_planning_and_execution()`.
3. Read `execution_orchestrator.py`. Confirmed Message actions flow through `_dispatch_single_action` → `confirm_and_dispatch` → `ActionExecutor`.
4. Read `__main__.py`. Confirmed `logging.basicConfig(..., force=True)` configures a `StreamHandler(sys.stderr)` at startup.
5. Read `shell_adapter.py` line 289 comment. This is a preventive note about stdin handling in subprocesses, not related to the Tee logging bug.
6. Root cause hypothesis: Tee.__exit__ does not revert the root logger handler change, leaving a StreamHandler pointing to the old TeeWriter (with closed log_file) on the root logger after exit. Post-exit logging attempts cause ValueError.
7. MRE execution (initial): Created `spikes/debug/22-io-closed-mre.py` that installs Tee, logs during, exits, then logs after. Initial MRE used try/except around logger.info() which FAILED to detect the ValueError because Python's logging module catches handler errors internally via handleError() and does NOT propagate them to the caller.
8. Refined understanding: The ValueError IS triggered but it's caught by logging's internal error handler and printed as a "Logging error" traceback to stderr. The bug affects users by polluting stderr with ugly tracebacks during Message actions after Tee exit, rather than crashing the process.
9. Refined MRE: Updated to capture stderr via redirect_stderr and search for "I/O operation on closed file" pattern. This correctly detects the bug even though the exception doesn't propagate.
10. Shadow file fix: Created `spikes/debug/shadow_io.py` that saves old root logger handlers in Tee.__enter__ (without closing them) and restores them in Tee.__exit__. This mirrors the save/restore pattern already used for stdout/stderr.
11. Import issue (Turns 6-8): The MRE import `from spikes.debug.shadow_io import Tee` required `spikes/` and `spikes/debug/` to be Python packages and the project root to be on sys.path. Added `__init__.py` files and fixed sys.path to include project root.
12. Shadow verification (Turn 9): MRE with --shadow executed successfully. The shadow fix PASSED: logging after Tee exit did NOT produce "I/O operation on closed file" errors. The old handlers were properly restored, and post-exit logging succeeded cleanly.
13. Baseline confirmation (Turn 9): MRE without --shadow confirmed the bug: "I/O operation on closed file" was detected in stderr after Tee exit in the real code. The causal model is fully verified.

## Solution
### Root Cause
`Tee.__enter__` replaces all root logger handlers with a new `StreamHandler(sys.stderr)` (where `sys.stderr` is the Tee proxy) to ensure logging flows through the Tee into the history log. However, `Tee.__exit__` restores `sys.stdout`/`sys.stderr` and closes the log file, but does NOT revert the root logger handler change. After Tee exit, the root logger still has a `StreamHandler` pointing to the old `_TeeWriter`, whose `_log_file` is now closed. Any subsequent `logger.info()` call triggers:
`StreamHandler.emit()` → `_TeeWriter.write()` → `self._log_file.write(clean)` → `ValueError: I/O operation on closed file`.

Python's logging module catches the exception internally and prints a "Logging error" traceback to stderr — polluting session output but not crashing the process. The user sees this as ugly error output during Message actions after a planning+execution cycle ends.

This is a **Context Manager Resource Leak** — the `__enter__` method modifies global state (logging root handlers) but `__exit__` fails to restore it, mirroring the same save/restore pattern already used for `sys.stdout`/`sys.stderr`.

### Proven Fix (shadow-verified)
In `Tee.__enter__`: save the original handlers WITHOUT closing them (they were already closed in the buggy version).
In `Tee.__exit__`: remove the Tee handler we added, then re-add the saved handlers.

This mirrors the exact save/restore pattern already used for `sys.stdout`/`sys.stderr`. The fix was verified via shadow file at `spikes/debug/shadow_io.py`. The MRE with `--shadow` flag confirmed that after Tee exit, logging succeeds without `"I/O operation on closed file"` errors.

### Preventative Measures
1. **Context Manager Resource Discipline**: Any context manager that modifies global state(s) in `__enter__` MUST revert those modifications in `__exit__`, following the save/restore pattern. This is a generalizable class of bug.
2. **Audit All Context Managers**: A quick audit of the codebase confirms Tee is the only context manager modifying global state (logging root handlers). All other `__enter__`/`__exit__` pairs manage local resources only.
3. **Protocol Awareness**: When wrapping `StreamHandler` streams, always consider what happens when the wrapper stream is torn down but the handler persists.
