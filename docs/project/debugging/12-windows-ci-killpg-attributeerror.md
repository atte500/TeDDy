# Bug: Windows CI fails with AttributeError on os.killpg mock
- **Status:** Unresolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
On Windows CI, tests in `tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py` fail with:
`AttributeError: <module 'os' (frozen)> does not have the attribute 'killpg'`
This is because `os.killpg` does not exist on Windows and `mock.patch("os.killpg")` throws an error.

**MRE:** `pytest tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py` on Windows (or an OS-independent MRE that simulates Windows).

## Diagnostic Analysis
### Causal Model
`ShellAdapter` uses `os.killpg` to clean up child processes on POSIX, but uses `process.kill()` on Windows. The tests `test_execute_handles_timeout_with_partial_output` and `test_execute_handles_timeout_without_output` in `test_shell_adapter_timeout.py` hardcode a `mock.patch("os.killpg")`. On Windows, `mock.patch` attempts to locate the attribute `killpg` on `os` to save its state. Since it does not exist, an `AttributeError` is raised before the test logic even begins.

### Discrepancies
None.

### Investigation History
