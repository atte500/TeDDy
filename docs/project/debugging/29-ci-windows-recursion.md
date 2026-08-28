# Bug: Windows CI RecursionError in `test_flush_stdin_uses_msvcrt_when_termios_missing`

- **Status:** Unresolved
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
(none yet)

### Investigation History
1. Remote probe triggered via workflow `debug.yml` (run 33154174110, job 98792899329). The probe executed `uv run pytest` on Windows CI. Log output confirmed the `RecursionError: maximum recursion depth exceeded` with the same stack trace as the original CI failure. The root cause is that the test's `_import_fails_for_termios` side effect calls `__import__(name, ...)` for non-`termios` imports, but since `builtins.__import__` is patched, this calls back into the mock, causing infinite recursion. Observation: The bug is fully reproduced on Windows CI. The fix must change the test's side effect to use `builtins.__import__` directly (saving a reference before patching) instead of calling the global `__import__`.

2. Created shadow test file `spikes/debug/shadow_test_console_ask_loop_stdin_flush.py` with fix applied: changed `_import_fails_for_termios` to use `importlib.__import__` to bypass the mocked `builtins.__import__`. Updated probe.sh to run the shadow file. Pending remote probe verification.

## Solution

(none yet)