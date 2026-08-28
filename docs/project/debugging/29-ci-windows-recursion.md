# Bug: Windows CI RecursionError in `test_flush_stdin_uses_msvcrt_when_termios_missing`

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected:** The test `test_flush_stdin_uses_msvcrt_when_termios_missing` should pass (green) when run on Windows, verifying that `_flush_stdin` falls back to `msvcrt` when `termios` is unavailable.

**Actual:** The test fails with `RecursionError: maximum recursion depth exceeded` on Windows CI (Python 3.14.7). The traceback shows infinite recursion between the mocked `builtins.__import__` and the custom side effect `_import_fails_for_termios`.

**Reproduction Steps:**
1. Run the test on Windows (or any environment where `msvcrt` is importable, but `termios` is mocked as missing).
2. Alternatively, run the test locally with the mocked import side effect; the same RecursionError should occur.

## Context & Scope

### Regressing Delta
N/A – This appears to be a pre-existing test design flaw, not a regression from recent changes.

### Environmental Triggers
- The test patches `builtins.__import__` with a custom `side_effect`.
- The production code (`_flush_stdin`) attempts `import msvcrt`.
- The side effect calls `return __import__(name, *args, **kwargs)` for non-`termios` imports, which goes back to the **mocked** `__import__`, causing infinite recursion.

### Ruled Out
- The production code (`_flush_stdin`) is correct; the issue is solely in the test side effect implementation.

## Diagnostic Analysis

### Causal Model
- Test uses `patch("builtins.__import__", side_effect=self._import_fails_for_termios)`.
- When `_flush_stdin` runs `import msvcrt`, the mock intercepts the call.
- `_execute_mock_call` invokes `_import_fails_for_termios`.
- Since `name != "termios"`, the side effect executes `return __import__(name, *args, **kwargs)`.
- `__import__` inside the side effect resolves to the **mocked** function (because the patch is still active), causing `_execute_mock_call` → side effect → `__import__` → mock → ... → recursion.

### Discrepancies
- No discrepancies found. The Causal Model accurately predicted the root cause (mocked `__import__` recursion). The shadow file fix (using `importlib.__import__`) was verified to resolve the issue on Windows CI.

### Investigation History
1. Remote probe triggered via workflow `debug.yml` (run 33154174110, job 98792899329). The probe executed `uv run pytest` on Windows CI. Log output confirmed the `RecursionError: maximum recursion depth exceeded` with the same stack trace as the original CI failure. The root cause is that the test's `_import_fails_for_termios` side effect calls `__import__(name, ...)` for non-`termios` imports, but since `builtins.__import__` is patched, this calls back into the mock, causing infinite recursion. Observation: The bug is fully reproduced on Windows CI. The fix must change the test's side effect to use `builtins.__import__` directly (saving a reference before patching) instead of calling the global `__import__`.

2. Created shadow test file `spikes/debug/shadow_test_console_ask_loop_stdin_flush.py` with fix applied: changed `_import_fails_for_termios` to use `importlib.__import__` to bypass the mocked `builtins.__import__`. Updated `probe.sh` to run the shadow file. Remote probe (workflow run 33154345205) confirmed the test PASSES on Windows CI with no RecursionError. The Windows job completed successfully (green checkmark) and the pytest output shows "1 passed". The fix is verified without modifying production code.

## Solution

**Root Cause:** The test's `_import_fails_for_termios` static method, used as a `side_effect` for `patch("builtins.__import__")`, called the global `__import__()` for non-`termios` imports. Since `builtins.__import__` was patched, this call recursed back into the mock, causing infinite recursion (RecursionError).

**Fix:** Replace `return __import__(name, *args, **kwargs)` with `return importlib.__import__(name, *args, **kwargs)`. The `importlib` module holds its own reference to the real `__import__` builtin, so calling it bypasses the mock and prevents recursion.

**Systemic Prevention:** This class of bug (mock recursion when a side effect calls the patched function via the global name) can be prevented by enforcing a rule: when writing custom `side_effect` functions for `patch("builtins.__import__")`, always use `importlib.__import__` to delegate to the real import mechanism. Alternatively, save a reference to the original `__import__` before patching.

**Categorical Audit Findings:**
- Searched for `patch.*builtins.__import__` across all `tests/` and `src/` — only one match: the failing test file `tests/suites/unit/adapters/outbound/test_console_ask_loop_stdin_flush.py`.
- Searched for custom `_import_fails_*` function names — only the one method in the failing test file (and its shadow copy).
- Searched for `__import__` calls inside test code that could serve as side effects — no other instances found.
- **Conclusion:** The bug is isolated to a single test file. The fix is low-risk and does not open the door to similar failures elsewhere.
