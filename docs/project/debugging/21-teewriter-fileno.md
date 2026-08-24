# Bug: TeeWriter missing fileno attribute
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When a session is active and the Tee is installed (wrapping sys.stdout/sys.stderr with `_TeeWriter`), any code that calls `.fileno()` on either sys.stdout or sys.stderr crashes with: `'_TeeWriter' object has no attribute 'fileno'`. The user reported this occurring during a Pathfinder `## Message` turn after resuming a session, but it likely also happens in normal session flow.

Expected: The system should handle `fileno()` calls gracefully (either by implementing the method or by guarding callers).
Actual: AttributeError is raised, breaking the session.

## Context & Scope
### Regressing Delta
The `_TeeWriter` class (introduced in commit 35fb6648 / 094243d7 revert cycle) was designed to `write()`, `flush()`, and `isatty()` on the wrapped streams. It does NOT implement `fileno()`. The regression was introduced when `_TeeWriter` was created — it was never designed to be a complete file-like wrapper. The Tee is installed during session execution in `session_lifecycle_manager.py` and `session_orchestrator.py`.

### Environmental Triggers
- A session must be running with Tee installed (sys.stdout / sys.stderr replaced with `_TeeWriter`).
- Some code must call `.fileno()` on the wrapped stream. Known triggers: `rich.Console` (used in ConsoleInteractorAdapter), `typer.echo()` / `typer.secho()`.
- Reproducible on macOS Darwin (primary dev platform).

### Ruled Out
- Our own code does NOT call `.fileno()` on stdout/stderr (only on stdin, with guards).
- The error is not related to sys.stdin (which is never wrapped by Tee).

## Diagnostic Analysis
### Causal Model
When a session starts, `Tee.__enter__()` replaces `sys.stdout` and `sys.stderr` with `_TeeWriter` instances that wrap the originals. `_TeeWriter` implements `write()`, `flush()`, `isatty()`, and `encoding`, but NOT `fileno()`. When third-party output libraries (typer, rich) attempt to inspect terminal capabilities or render output, they call `.fileno()` on these streams. Since `_TeeWriter` lacks this method, Python raises `AttributeError`.

### Discrepancies
- Initially hypothesized that `typer.echo` or `rich.Console` would trigger the crash. MRE showed they do NOT. (Resolved: These libraries capture file descriptors at initialization time, before Tee wraps the streams. `Console(stderr=True)` in `ConsoleInteractorAdapter` is created in `__init__`, which runs before Tee is installed. Therefore they write to the original stderr file descriptor directly, bypassing the Tee wrapper entirely.)

### Investigation History
1. Located `_TeeWriter` in `src/teddy_executor/core/utils/io.py`. Confirmed it has no `fileno()` method.
2. Searched our codebase for `.fileno()` calls. Only found calls on `sys.stdin` (guarded with try/except).
3. Searched for `os.isatty` calls: `shell_adapter.py` uses `sys.stdout.isatty()` and `sys.stderr.isatty()` — these would pass through `_TeeWriter.isatty()` fine.
4. Traced session output path: `ConsoleInteractorAdapter.display_message()` uses `self._console.print(message)` where `_console = rich.Console(stderr=True)`. Hypothesis: Rich Console calls `.fileno()` on stderr during init or render.
5. `typer.echo()` and `typer.secho()` use rich under the hood and could also trigger `fileno()` calls.
6. MRE execution: Installed Tee and tested `.fileno()` on stdout/stderr. Both direct calls raised AttributeError as expected. Surprising finding: typer.echo and rich.Console.print did NOT fail. Investigation revealed they capture file descriptors at initialization (before Tee), so they bypass the Tee wrapper.
7. Codebase wide search for `select`, `poll`, `asyncio`, and `fcntl` usage found NO calls on stdout/stderr. Only `select` in unrelated textual app code.
8. Exhaustive search for all `.fileno()` calls in the project confirms only two sites: both on `sys.stdin` with try/except guards. No code in this project calls `.fileno()` on stdout/stderr.
9. Root cause isolated: `_TeeWriter` lacks `fileno()` method. The exact caller in the user's session is unknown but could be `prompt_toolkit` (recently added for arrow key navigation) or other terminal introspection. The fix is to implement `fileno()` on `_TeeWriter`.
10. Shadow file verification: Created `spikes/debug/shadow_io.py` with `fileno()` added to `_TeeWriter`. Enhanced MRE to test both real and shadow Tee. Shadow verification PASSED: `sys.stdout.fileno()` returned 1, `sys.stderr.fileno()` returned 2, `logging.StreamHandler` through Tee succeeded without AttributeError, `os.isatty(sys.stdout.fileno())` returned False (expected for test environment). Fix empirically proven without modifying `src/` or `tests/`.

## Solution
### Root Cause
`_TeeWriter` is a file-like wrapper that implements `write()`, `flush()`, `isatty()`, and `encoding` — but NOT `fileno()`. Python's `TextIO` protocol includes `fileno()` as an expected method. When any code (e.g., `os.isatty()` on a stream, `prompt_toolkit` terminal checks, or other terminal introspection libraries) calls `.fileno()` on a Tee-wrapped `sys.stdout` or `sys.stderr`, Python raises `AttributeError` because the method is missing.

The bug was introduced when `_TeeWriter` was created (commits 35fb6648 / 094243d7 revert cycle). It was designed for basic output duplication and logging, not as a complete `TextIO` replacement. The exact trigger in the user's session is unknown (likely `prompt_toolkit`, `typer`, or `rich` during terminal capability checks), but any code calling `.fileno()` on Tee-wrapped streams will encounter this crash.

### Proven Fix
Add a `fileno()` method to `_TeeWriter` that delegates to the original stream:

```python
def fileno(self) -> int:
    """Delegate fileno to the original stream."""
    return self._original.fileno()
```

This was verified via the Shadow File methodology: a replica of `io.py` with the added method was placed at `spikes/debug/shadow_io.py`. The MRE tested the shadow Tee and confirmed `sys.stdout.fileno()` returns 1, `sys.stderr.fileno()` returns 2, `logging.StreamHandler` operates without error, and `os.isatty(fileno())` works correctly.

### Preventative Measures
1. **Complete TextIO Protocol**: Any file-like wrapper that implements `write()`, `flush()`, `isatty()`, and `encoding` should also implement `fileno()` to match the `TextIO` protocol. This is a single-line delegation to the original stream.
2. **Protocol Verification**: Consider adding a runtime check or abstract base class (`io.TextIOBase`) verification for future stream wrappers to ensure the full protocol is implemented.
3. **Guard at Call Sites**: While not necessary after the fix, any code calling `fileno()` on streams that may be proxied should guard with `getattr(stream, 'fileno', None)` as a belt-and-suspenders approach.
