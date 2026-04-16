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
- `pytest` is executing with `xdist` (`-n auto`) and `pytest-timeout`.
- Ubuntu uses `fork` by default for multiprocessing.
- A background thread, lock, external syscall, or sub-process within one of the tests is deadlocking or preventing the worker from progressing.

### Discrepancies
- The previous TTY guard fix did not resolve the hang.
- [2026-04-16] Wiring regression: `IPlanReviewer` resolved to `ConsolePlanReviewer` in tests. (resolved: Aggressive `PYTEST_CURRENT_TEST` guard in `reviewer.py` removed, but then reinstated and dynamically patched via `monkeypatch.delenv` to safely bypass).
- `ShellAdapter` uses `preexec_fn` which causes deadlocks. (resolved: Checked `src/teddy_executor/adapters/outbound/shell_adapter.py`. It uses `start_new_session=True`, NOT `preexec_fn`.)

### Investigation History
- [2026-04-16] Case reopened. Issue persists in CI environment. Preparing Remote CLI Protocol.
- [2026-04-16] Attempted remote monitoring via `gh run view`. Encountered `null` job IDs during early workflow initialization. Resetting and retrying with robust polling.
- [2026-04-16] Identified `preexec_fn` in `ShellAdapter` as the likely cause of Ubuntu deadlock due to `fork()` semantics in `pytest-xdist`.
- [2026-04-16] Identified Windows worker crash in `WebScraperAdapter` tests, likely due to `trafilatura`/`lxml` binary instability in parallel tests.
- [2026-04-16] **RED STATE RESET:** Discovered that a planned `EDIT` to remove `preexec_fn` from `ShellAdapter` was skipped due to a prior validation failure. The `preexec_fn` remains active in the codebase.
- [2026-04-16] **Correction:** Read `shell_adapter.py`. It does NOT contain `preexec_fn`. It uses `start_new_session=True`. The previous RED STATE diagnosis was based on a false premise. The root cause of the Ubuntu hang is unknown.
- [2026-04-16] **RED STATE RESET:** Attempted to use a Remote CLI watchdog script on temporary branches to catch the hanging test in CI. The workflow runs were too slow, and the logs were inaccessible while running. The approach created excessive branch clutter and was manually aborted.
- [2026-04-16] Executed strict Remote Probing Protocol (Rule 14). Ran `pytest -n 0 -vv -s --setup-show` on transient branches to isolate the hang.
- [2026-04-16] Discovered the hang is **highly non-deterministic**. It randomly strikes during the setup phase of different tests (e.g., hanging at `SETUP F env` for `test_regression_read_action_suspend`, and later at `SETUP F container` for `test_confirm_action_handles_eof_error`).
- [2026-04-16] Since the hang occurs even with `xdist` disabled (`-n 0`), it is likely caused by a leaked background thread or `asyncio`/`anyio` event loop from a previous test (suspected: Textual `App` instances leaving unresolved worker threads) deadlocking Pytest's fixture teardown/setup on Ubuntu workers. (resolved: Tests `test_regression_research_list_parsing` and `test_regression_reactivity_on_edit` instantiate `ReviewerApp` without using `app.run_test()`, leaving Textual's background tasks dangling in the `anyio` thread pool, causing a deadlock on Ubuntu's `fork()` teardown).
- **Current Workspace State:** Workspace hard-reset to `main`. All `debug/*` branches deleted.
