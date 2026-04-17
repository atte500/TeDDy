# Bug: Windows CI WinError 10106 in Lazy Loading Test

- **Status:** Unresolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
Expected: `test_web_scraper_github_url_does_not_import_trafilatura` passes on all platforms.
Actual: Fails on Windows CI with `AssertionError: trafilatura was imported prematurely for a GitHub URL!` because the subprocess returns 1. The stderr shows `OSError: [WinError 10106] The requested service provider could not be loaded or initialized` during `import _overlapped`.

## Context & Scope
### Regressing Delta
Changes in `src/teddy_executor/adapters/outbound/web_scraper_adapter.py` and the addition of `tests/suites/integration/core/services/test_lazy_loading_integration.py`.

### Environmental Triggers
- OS: Windows (CI)
- Mechanism: Subprocess execution in pytest.

### Ruled Out
- N/A

## Diagnostic Analysis
### Causal Model
The regression test `test_web_scraper_github_url_does_not_import_trafilatura` used a subprocess to verify that `trafilatura` was not imported during a GitHub scrape.
Inside the subprocess, it used the `responses` library to mock network requests.
On Windows CI runners, importing `responses` or invoking `requests` can trigger the initialization of the Windows network stack (Winsock), which involves importing the `_overlapped` C extension.
In certain CI environments, this initialization fails with `OSError: [WinError 10106]`.
The subprocess crashed, and the test incorrectly interpreted the crash as a logic failure.

### Discrepancies
- [x] Subprocess returns 1, but logs show an OSError rather than a logic failure. (resolved: Verified that exit code 1 was caused by the crash during `_overlapped` import).
- [x] Is `responses` necessary for the lazy-loading test? (resolved: No, `unittest.mock.patch` can be used to avoid network stack initialization).

## Solution
### Implemented Fixes
- Refactored `test_web_scraper_github_url_does_not_import_trafilatura` in `tests/suites/integration/core/services/test_lazy_loading_integration.py` to use `unittest.mock.patch` instead of `responses`.
- Added improved diagnostic logging to the subprocess execution to catch environment-specific crashes.

### Prevention
- Future lazy-loading tests requiring isolation should prefer `unittest.mock` over network-level libraries in subprocesses to ensure cross-platform stability.
