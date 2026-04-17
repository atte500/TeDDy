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
The regression test `test_web_scraper_github_url_does_not_import_trafilatura` uses a subprocess to verify that `trafilatura` is not imported during a GitHub scrape.
Investigation of CI failures shows that `import unittest.mock` (used in the fix) transitively imports `asyncio` (for `AsyncMock` support). On Windows, `asyncio` imports `asyncio.windows_events`, which imports the `_overlapped` C extension.
In restricted Windows CI environments, this chain triggers `OSError: [WinError 10106]`.

Therefore, any library that imports `asyncio` (including `unittest.mock` and potentially `responses`) can cause this crash in the subprocess.

### Discrepancies
- [x] Subprocess returns 1, but logs show an OSError rather than a logic failure. (resolved: Verified that exit code 1 is caused by the crash during `_overlapped` import).
- [x] Is `responses` necessary for the lazy-loading test? (resolved: No, but its replacement `unittest.mock` also triggers the same issue).
- [ ] Can we test lazy-loading without `asyncio`? (resolved: Yes, by using manual monkeypatching instead of high-level mocking libraries).

## Solution
### Implemented Fixes
- Refactored `test_web_scraper_github_url_does_not_import_trafilatura` in `tests/suites/integration/core/services/test_lazy_loading_integration.py` to use `unittest.mock.patch` instead of `responses`.
- Added improved diagnostic logging to the subprocess execution to catch environment-specific crashes.

### Prevention
- Future lazy-loading tests requiring isolation should prefer `unittest.mock` over network-level libraries in subprocesses to ensure cross-platform stability.
