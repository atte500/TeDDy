# Bug: Windows CI Worker Crashes

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

Pytest-xdist workers crash on Windows CI when running specific tests.

### Failing Tests:
1. `tests/suites/acceptance/test_session_resume_robustness.py::test_start_enters_continuous_loop`
2. `tests/suites/integration/adapters/outbound/test_web_scraper_adapter.py::test_get_content_falls_back_on_403_error`

### Error Output:
```
worker 'gw2' crashed while running 'tests/suites/acceptance/test_session_resume_robustness.py::test_start_enters_continuous_loop'
worker 'gw3' crashed while running 'tests/suites/integration/adapters/outbound/test_web_scraper_adapter.py::test_get_content_falls_back_on_403_error'
```

## System Model

### Understanding
Initial triage: The crashes occur on Windows 3.11.9. Worker crashes in `pytest-xdist` often indicate a segmentation fault (often `lxml`), an unhandled exception in a C extension, or a hard exit that bypasses pytest's error handling.

**Observed Crash Points:**
1. `test_start_enters_continuous_loop`: Multi-turn loop in `handle_new_session`. Suspect `click.prompt` / `EOFError` handling or an infinite loop when `stdin` is exhausted on Windows.
2. `test_get_content_falls_back_on_403_error`: `trafilatura` usage with `patch`. Suspect `lxml` (or `htmldate` / `courlan` dependencies) segfault during import on Windows CI.

### Discrepancies
None.

## Solution

### Implemented Fixes
- **WebScraper Isolation:** Refactored `test_web_scraper_adapter.py` to use string-based patching for `trafilatura`. This prevents the library (and its `lxml` dependency) from being imported at the module level during test collection, isolating the Windows workers from potential binary instability/segfaults.
- **Loop Termination Guard:** Hardened the `while True` loops in `session_cli_handlers.py` to explicitly handle `None` returns from `orchestrator.resume`, ensuring graceful termination when `stdin` is exhausted (e.g., during CI runs).
- **CWD Resilience:** Enhanced the `os.chdir` cleanup in `conftest.py` with a try/except block to ensure worker stability even if a test fails in a way that corrupts the filesystem state.

### Prevention
- Future tests involving heavy third-party libraries with binary extensions (like `trafilatura`, `lxml`, `litellm`) MUST use string-based patching and avoid module-level imports in test files to maintain worker stability on Windows CI.
- Continuous loops in CLI handlers MUST be explicitly tested for EOF/Empty input termination.
