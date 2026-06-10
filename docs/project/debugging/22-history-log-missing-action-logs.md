# Bug: History.log Missing Action Log Details
- **Status:** Resolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [docs/project/slices/00-25-history-log.md](/docs/project/slices/00-25-history-log.md)
- **Specs:** [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md)

## Symptoms
- **Expected:** The `history.log` file in a session root should contain all console output from a turn, including action log lines like `READ - Read the full session orchestrator...` and `SUCCESS`.
- **Actual:** Only turn transition metadata (e.g., `[01] teddy-work-2 | Waiting for pathfinder to respond... • Model: ... • Context: ...`) appears in `history.log`. The detailed action log lines are missing.
- **Minimal Reproduction Steps:** Start a session, let the planner generate a plan and execute it. Check `history.log` after the first turn. The turn header is present but action logs are omitted.

## Context & Scope
### Regressing Delta
The bug exists in the current implementation of history.log (slice 00-25). The `Tee` class in `src/teddy_executor/core/utils/io.py` correctly replaces `sys.stdout`/`sys.stderr`. However, the logging module's `StreamHandler` (configured in `src/teddy_executor/__main__.py` at line 42-45) was created with a reference to the original `sys.stderr`. When Tee replaces `sys.stderr`, the handler continues writing to the original stream, bypassing the Tee proxy. No specific commit introduced this; it's a design oversight of the Tee capture mechanism.

### Environmental Triggers
- Any environment where logging is configured to write to `sys.stderr` (which is always the case in this project).
- The bug manifests whenever a session executes actions (i.e., when Tee is installed).

### Ruled Out
- Tee itself works correctly (confirmed by turn header capture).
- Console output via `Rich.Console(stderr=True)` is captured correctly because it reads the current `sys.stderr` at print time.
- stdout-based output is captured correctly (Tee replaces both streams).

## Diagnostic Analysis
### Causal Model
1. At module import time, `logging.basicConfig` creates a `StreamHandler` that stores a reference to the *original* `sys.stderr` Python stream object.
2. Later, `SessionOrchestrator.execute()` installs the `Tee`, which replaces `sys.stdout` and `sys.stderr` with its proxy writers (`_TeeWriter`).
3. The `ActionDispatcher` logs action descriptions and statuses via `logger.info()`.
4. The logging handler writes to its cached original `sys.stderr`, bypassing the Tee proxy → output appears on console but NOT in `history.log`.
5. Turn transition headers are printed via `ConsoleInteractor.display_message()` → `self._console.print()` → Rich Console reads the *current* `sys.stderr` (the Tee proxy) → output appears in both console and `history.log`.

### Discrepancies
- Logging handler writes to original stderr, not Tee proxy. Expected: handler should write to current sys.stderr. (Unresolved)

### Investigation History
(None yet)

## Solution

### Root Cause
The `logging.StreamHandler` is configured in `__main__.py` at module import time with `handlers=[logging.StreamHandler(sys.stderr)]`. This handler stores a direct reference to the **original `sys.stderr`** Python stream object. When `Tee.__enter__()` later replaces `sys.stderr` with a `_TeeWriter` proxy that tees output to both stderr and `history.log`, the logging handler continues writing to its cached original stream, completely bypassing the Tee proxy.

By contrast, `typer.echo(err=True)` and `Rich.Console(stderr=True).print()` read the **current** `sys.stderr` at call time, so they are correctly captured by the Tee.

### Fix
Modify `Tee.__enter__()` to update all existing `logging.StreamHandler` instances that reference the original `sys.stdout` or `sys.stderr` to use the new Tee proxy streams. Specifically:

1. After replacing `sys.stdout`/`sys.stderr` with `_TeeWriter` instances, iterate over `logging.root.handlers`.
2. For each `logging.StreamHandler` whose `self.stream` matches the previously saved original stream (`self._original_stderr` or `self._original_stdout`), replace `handler.stream` with the current `sys.stderr` or `sys.stdout` (the new `_TeeWriter`).
3. The `_TeeWriter` implements `write()` and `flush()`, which is sufficient for `StreamHandler`.
4. No revert is needed in `__exit__()` because restoring `sys.stderr`/`sys.stdout` to the original streams will cause the handler to automatically use the restored stream (the handler's stream attribute still points to the `_TeeWriter` which is no longer in the stream chain, but after teardown, the `_TeeWriter` will write to the restored original via its internal reference).

This ensures that logging output flows through the Tee and is captured in `history.log`.

### Preventative Measures
To prevent this class of issue globally:
1. **Audit all module-level stream captures:** No other places in the codebase cache `sys.stdout`/`sys.stderr` at import time (confirmed via categorical audit). The `Console(stderr=True)` in `console_interactor.py` reads the current stderr at print time, so it's safe.
2. **Defensive logging handler reconfiguration:** In the future, any new code that configures logging with a `StreamHandler` pointing to `sys.stdout`/`sys.stderr` must be aware that the Tee will bypass it. Consider making logging handler configuration dynamic (lazy) rather than static at import time.
3. **Add regression test:** The MRE `spikes/debug/22-history-log-mre.py` serves as a permanent regression test to ensure logging output is captured by the Tee.
