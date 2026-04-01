# MRE: Windows CI Worker Crash

- **Status:** Resolved
- **Failure:** pytest-xdist workers crash on `windows-latest` with "Not properly terminated".

## 1. Failure Context
The CI pipeline for `windows-latest` fails consistently across multiple acceptance tests. The workers die abruptly, suggesting a hard exit or a fatal exception that bypasses standard pytest error handling.

## 2. Steps to Reproduce
1. Push a branch to GitHub.
2. Observe `windows-latest` job in `test-suite`.
3. Workers `gw0`, `gw1`, `gw2`, `gw3` crash during acceptance tests.

## 3. Expected vs. Actual Behavior
- **Expected:** Tests pass or fail with a standard traceback.
- **Actual:** Workers terminate unexpectedly, causing `pytest-xdist` to report "node down: Not properly terminated".

## 4. Relevant Code
- `src/teddy_executor/adapters/outbound/shell_adapter.py` (Windows process execution)
- `src/teddy_executor/adapters/outbound/console_interactor.py` (UI/Terminal handling)
- `docs/architecture/ARCHITECTURE.md` (Notes on Windows `exit /b` handling)

## 5. Investigation Log
> **Hypothesis**: Recent changes to shell command isolation on Windows are causing the parent Python process to terminate when a sub-command exits.
> **Experiment**: Analyze `ShellAdapter` implementation for Windows.
> **Observation**: `ShellAdapter` uses complex wrapping `(call ... || cmd /c ... exit 1)`.
> **Conclusion**: Potential, but `subprocess.run` should isolate this.

> **Hypothesis**: `pyperclip` access in a daemon thread (via `echo_and_copy`) is causing a hard crash on Windows CI.
> **Experiment**: Analyze `CliTestAdapter`.
> **Observation**: `CliTestAdapter` uses `--no-copy` for most commands.
> **Conclusion**: Less likely to be the primary cause for worker crashes during tests.

> **Hypothesis**: The Windows-specific command wrapping logic in `ShellAdapter` using `(cmd /c ... || cmd /c ... & exit 1)` causes a process-level termination that crashes `pytest-xdist` workers on Windows CI.
> **Experiment**: Run isolated reproduction script `spikes/debug/repro_windows_shell_crash.py` in Windows environment.
> **Observation**: Logic is present but `subprocess.run` isolates the exit.
> **Conclusion**: Less likely to be the primary cause.

> **Hypothesis**: `os.chdir` calls in integration tests are not properly restored, disrupting other workers in `pytest-xdist` on Windows.
> **Experiment**: Run `tests/suites/integration/test_naked_leak.py` with two tests: one that changes CWD and one that verifies it.
> **Observation**: `test_verify_leak_naked` failed as expected, confirming the CWD was not restored to the project root.
> **Conclusion**: Confirmed. Naked `os.chdir` leaks global state. This causes "Not properly terminated" worker crashes on Windows CI because workers cannot clean up directories that are still locked as a CWD by other workers.

## 6. Proposed Fix

| Strategy | Pros | Cons | Regression Risk |
| :--- | :--- | :--- | :--- |
| **1. Refactor to `monkeypatch.chdir`** | Standard pytest approach; thread-safe; automatic restoration. | Requires manual update of all leaky tests. | Low |
| **2. Global CWD Guard (conftest.py)** | Defensive "Stop the line" safety; protects against future leaks. | Slightly more global overhead. | Very Low |

**Primary Recommendation:** Combine both. Refactor the known leaks and add the global guard to ensure future stability on Windows CI.

## 7. Root Cause Analysis
Multiple integration tests in `tests/suites/integration/core/services/test_session_validation_integration.py` were found to use `os.chdir()` directly without a restoration mechanism. In a concurrent `pytest-xdist` environment (especially on Windows where file locking is strict), this leads to race conditions and "Not properly terminated" crashes.

## 8. Implementation Notes
- **Surgical Fix:** Replaced `os.chdir(tmp_path)` with `monkeypatch.chdir(tmp_path)` in `tests/suites/integration/core/services/test_session_validation_integration.py`. This ensures that even without the global guard, these tests are internally isolated.
- **Systemic Fix:** Added an `autouse=True` fixture `clean_test_env` in `tests/conftest.py`. This fixture captures the project root before every test and restores it during teardown, preventing any leaked `os.chdir` from affecting subsequent tests or crashing `pytest-xdist` workers on Windows.
- **Verification:** Reproduced the leak with an isolated "naked" test that changed CWD and confirmed it persisted. Verified that the systemic fix restored the CWD and the full suite passed on macOS.
