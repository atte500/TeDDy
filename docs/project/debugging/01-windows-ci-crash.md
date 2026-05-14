# Bug: Windows CI xdist worker crash in session resume test
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [docs/project/slices/00-09-windows-subprocess-concurrency-fix.md](/docs/project/slices/00-09-windows-subprocess-concurrency-fix.md)
- **Specs:** N/A

## Symptoms
Intermittent CI failures on Windows. The pytest xdist worker crashes with `[gwX] node down: Not properly terminated` while running tests such as `tests/suites/acceptance/test_session_resume_robustness.py::test_resume_auto_detects_latest_session`.

## Context & Scope
### Regressing Delta
The SUT SUT uses `subprocess.Popen` in `ShellAdapter` (and other adapters) to execute commands. When migrating to concurrent test execution (`pytest-xdist -n 4`), standard input pipe contention surfaced on Windows runners.

### Environmental Triggers
Occurs exclusively on Windows when tests run concurrently under `pytest-xdist`.

### Ruled Out
- Infinite loops in `typer.prompt` or `ConsoleInteractor`.
- `TextualPlanReviewer` TTY initialization.
- Pytest timeout thread deadlocks (the timeout merely reported the hang; it did not cause the node down).

## Diagnostic Analysis
### Causal Model
When tests run concurrently under `pytest-xdist` on Windows, the worker processes share captured standard I/O pipes. In `ShellAdapter._prepare_subprocess_kwargs`, `stdin` was explicitly redirected to `subprocess.DEVNULL` for POSIX platforms, but left to default (`None`, meaning inherit) on Windows.
When multiple concurrent tests execute `subprocess.Popen` simultaneously, `cmd.exe` or Python attempts to inherit the identical `stdin` pipe handle across multiple parallel subprocesses. This concurrency collision fatally crashes the xdist worker process with the `Not properly terminated` error.

### Discrepancies
- **Observation:** `timeout method: thread` appeared in logs, but no TimeoutExpired tracebacks. **Conflict:** The process was dying abruptly before the timeout could resolve it. (Resolved: Concurrent handle inheritance triggers a fatal Windows OS error that abruptly terminates the parent Python worker process, bypassing pytest entirely.)

### Investigation History
1. Synthesized CI logs and identified `gw2 node down` during the EXECUTE phase of tests.
2. Formulated hypothesis regarding `stdin` inheritance or `click.prompt` hanging.
3. Created a remote probe (`spikes/debug/remote_probe.sh`) running tests sequentially (`-n 0`) which passed 10/10 times, verifying concurrency trigger.
4. Updated probe to run concurrently (`-n 4`), successfully reproducing the crash.
5. Created a Sandbox Python Runner (`spikes/debug/mre_runner.py`) that monkey-patched `ShellAdapter._prepare_subprocess_kwargs` to force `stdin=subprocess.DEVNULL` on all platforms.
6. The test passed 10/10 runs concurrently on Windows. Hypothesis proven.

## Solution
The root cause is un-isolated `stdin` handles in subprocesses running on Windows under xdist.
The systemic solution is to explicitly enforce `stdin=subprocess.DEVNULL` for all automated/non-interactive `subprocess.Popen` and `subprocess.run` invocations across the codebase to prevent handle contention.
A systemic audit revealed similar vulnerabilities in `SystemEnvironmentAdapter`, `SystemEnvironmentInspector`, and `TextualPlanReviewerEditor`. These will be holistically addressed in Slice `00-09-windows-subprocess-concurrency-fix.md`.
