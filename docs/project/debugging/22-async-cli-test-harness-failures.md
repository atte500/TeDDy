# Bug: Async CLI Test Harness Failures

- **Status:** Unresolved
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [Slice 00-05: Planning Lifecycle & UI Visibility](/docs/project/slices/00-05-planning-lifecycle-visibility.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## Context & Scope

### Regressing Delta
The regression was introduced in the current staged changes, which represent an incomplete migration to an asynchronous architecture.
- **Component:** `src/teddy_executor/__main__.py`
- **Delta:** The `execute` CLI command was refactored to be a synchronous `def` function that internally calls `anyio.run()` to drive the underlying `async` service logic. However, the other session-related commands (`start`, `resume`, `plan`) were not updated and remain purely synchronous. This creates an inconsistent architecture where parts of the application are async-aware and others are not.

### Environmental Triggers
The issue is triggered exclusively within the `pytest` test environment when using the synchronous `typer.testing.CliRunner` to invoke the CLI.

### Ruled Out
- **Past Commits:** The issue is not present in the `git` history; it is a result of uncommitted work-in-progress.
- **`pytest-xdist` or `pyfakefs`:** Disabling these did not resolve the issue, indicating the problem is more fundamental to the sync/async interaction.

## Diagnostic Analysis

### Causal Model
The root cause of the systemic test suite failure is a fundamental conflict between a purely `async def` Typer command and the synchronous `typer.testing.CliRunner` used in the test harness.

1.  **Async Command Declaration:** A CLI command was declared directly as an `async def` function.
2.  **Synchronous Test Invocation:** The test harness uses `typer.testing.CliRunner`'s `invoke` method to call the command. This runner is purely synchronous.
3.  **Event Loop Mismatch:** The `CliRunner` does not create or manage an `anyio` event loop. When it invokes the command, it receives a coroutine object but has no mechanism to `await` it.
4.  **Unawaited Coroutine:** The coroutine is never awaited and its code never executes. This is confirmed by the `RuntimeWarning: coroutine ... was never awaited` emitted during the test run.
5.  **Symptom Cascade:** Because the command body does not run, any expected side effects (like printing to stdout) or calls to underlying services (which are often mocked) never occur. This leads to a wide variety of assertion failures (`AssertionError: assert '...' in ''`), broken mock assertions (`TypeError: cannot unpack NoneType`), and other downstream errors, all originating from the single root cause of the unawaited coroutine.

### Discrepancies
- The `AsyncTyperCliRunner` successfully invokes a minimal async command. (Resolved: The runner works, but the problem is that it's not being used by the 100+ tests that are failing).
- The global test suite fails with 120 errors after making the `execute` command async. This contradicts the expectation that a localized fix should not cause systemic regressions.
- **(New Discovery)** The `SessionOrchestrator.async_execute` method contains a latent bug: it passes the raw `plan_content` string to the `PlanValidator`, which expects a parsed `Plan` object. This causes an `AttributeError: 'str' object has no attribute 'actions'`. This bug was only exposed after the async invocation was fixed, as the code was previously unreachable.

### Investigation History
- **Initial MREs:** Confirmed `typer.testing.CliRunner` is incompatible with `async` commands and that `typer.main.get_command` strips `async` behavior, necessitating a custom solution.
- **RED State Reset (2026-04-23):** Initial attempts to build an `AsyncTyperCliRunner` failed repeatedly with misleading errors (`TypeError`, `AttributeError`, `SystemExit(2)`). After several iterations of probing and repair, a working fix for the runner was developed.
- **Suite Alignment Failure (2026-04-23):** After applying the fix for `AsyncTyperCliRunner` and verifying it with a single regression test, the global test suite was run. The result was a catastrophic failure of 120 tests. The failure was systemic, caused by the `execute` command being made asynchronous while the primary test harness (`CliTestAdapter`) remained synchronous. This created widespread issues with un-awaited coroutines and broken mock contracts. The Causal Model was invalidated, requiring a return to the investigation phase to address the core architectural conflict.
