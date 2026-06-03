# Bug: ShellAdapter Timeout Handling Regression
- **Status:** Unresolved
- **Milestone:** [Milestone 2: Stability & Polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [Slice 02-06: Orchestrator Hardening](/docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [Stability & Bugfixes](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
**Expected:** `ShellAdapter._handle_timeout` should detect interactive prompts from stderr patterns (e.g., "Unexpected EOF", "Input required from terminal") and return a standardized interactive prompt failure message (`FAILURE: Interactive prompt detected`). For non-interactive timeouts, it should preserve partial stdout/stderr output alongside the timeout message.

**Actual:** All timeout cases return only `[ERROR: Command timed out after X seconds]`, ignoring both the interactive prompt detection logic and the partial stdout/stderr preservation. Additionally, background execution tests fail because `Popen` is never called.

**Reproduction:** Run the following tests:
- `tests/suites/unit/adapters/outbound/test_shell_adapter_windows_interactive.py::TestHandleTimeout::test_timeout_with_unexpected_eof_detected`
- `tests/suites/unit/adapters/outbound/test_shell_adapter_windows_interactive.py::TestHandleTimeout::test_timeout_with_non_interactive_stderr_returns_timeout_message`
- `tests/suites/unit/adapters/outbound/test_shell_adapter_windows_interactive.py::TestHandleTimeout::test_cmd_c_wrapper_exit_propagation`
- `tests/suites/unit/adapters/outbound/test_shell_adapter_windows_interactive.py::TestHandleTimeout::test_timeout_with_input_required_detected`
- `tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py::test_execute_handles_timeout_with_partial_output`
- `tests/suites/unit/adapters/outbound/test_shell_adapter_background.py::test_execute_background_starts_popen_and_returns_pid`
- `tests/suites/unit/adapters/outbound/test_shell_adapter_background.py::test_execute_background_isolates_stdin`

## Context & Scope

### Regressing Delta
Three sequential shell-related commits constitute the regressing delta:
1. `8563b82b` – `feat(shell): detect interactive prompts via EOFError patterns` (Added `read error`, `Input/output error`, `Inappropriate ioctl` patterns to `_detect_interactive_prompt`)
2. `0335c11d` – `feat(shell): implement interactive prompt detection via os.setsid and EOFError patterns` (Replaced `os.setpgrp()` with `os.setsid()` in `preexec_fn`; added additional interactive detection patterns)
3. `3f84359c` – `feat(shell): implement Windows interactive prompt detection with direct-method test harness` (Added `test_shell_adapter_windows_interactive.py` test file)

The critical change: `preexec_fn` now calls `os.setsid()` instead of `os.setpgrp()`. This creates a new session, detaching from any controlling terminal. While this improves `/dev/tty` detection, it may have side effects on the subprocess environment during timeouts.

### Environmental Triggers
- **All platforms:** The failures occur on windows-latest, macos-latest, and ubuntu-latest, indicating a platform-independent logic error.
- **Mock-sensitive:** The failing tests use `unittest.mock` to simulate `Popen` objects and `communicate()` side effects. The `_handle_timeout` tests call the method directly with mock processes.
- **Test isolation:** The background tests (`test_execute_background_*`) patch `subprocess.Popen` but report `Called 0 times`.

### Ruled Out
- **Not platform-specific** – fails on all three CI OSes.
- **Not configuration-specific** – tests use mocked subprocesses.
- **Not a general test infrastructure issue** – 751 other tests pass.
- **Not a change in `_handle_timeout` logic** – the method body was not modified in the regressing commits; only `_detect_interactive_prompt` and `preexec_fn` changed.
- **Not a method signature change** – `_handle_timeout` signature unchanged.

## Diagnostic Analysis

### Causal Model
Three interdependent test mock misconfigurations caused 7 test failures across the ShellAdapter test suite:

1. **Constructor Binding of `_popen` (Primary Root Cause):** `ShellAdapter.__init__` caches `self._popen = subprocess.Popen` at construction time. When tests use `patch("subprocess.Popen")` globally, the patch has no effect because the adapter's instance variable already holds a direct reference to the real `subprocess.Popen` function. This causes:
   - Background tests: `self._popen(...)` always uses real `Popen` → mock never called → "Called 0 times" assertion failure.
   - Timeout partial-output test: Real subprocess spawned and timed out → real output doesn't match expected mock output.

2. **`_handle_timeout` Direct Test Mock Pattern (Secondary Root Cause):** Four tests in `TestHandleTimeout` call `_handle_timeout(process, 0.5)` directly. They pass `communicate.side_effect = [TimeoutExpired(...), (output, stderr)]`—a 2-element list designed for `_run_subprocess`'s flow (first communicate raises, second fallback succeeds). But `_handle_timeout` only calls `communicate` once. The first element (TimeoutExpired) is raised and caught by `_handle_timeout`'s own `except TimeoutExpired` block, causing stdout/stderr to be set to empty strings. The correct pattern is `communicate.return_value = (output, stderr)`.

3. **Consequence:** All 7 failing tests produce the same symptom: `_handle_timeout` returns `[ERROR: Command timed out after X seconds]` instead of the interactive prompt failure message or the expected partial output.

### Discrepancies
- `patch("subprocess.Popen")` has no effect on `adapter._popen`. (Resolved: `_popen` is bound at constructor time to the real `subprocess.Popen`; global patches of `subprocess.Popen` do not affect instance variables that already hold a direct reference. Probe 6 verified this.)
- `_handle_timeout` direct tests use 2-element `communicate.side_effect` list. (Resolved: `_handle_timeout` only calls `communicate` once, so the first element (TimeoutExpired) is raised and caught, wiping stdout/stderr. The correct pattern is `communicate.return_value`. Probes 1-4 verified the failure; Probe 5 verified the correct pattern.)
- Background and timeout tests broken due to `_popen` binding. (Resolved: fix applied via `patch.object(adapter, '_popen')` in 2 background tests and 1 timeout test.)

### Investigation History
1. Initial git log and CI scan identified failing commit `0335c11d` with 7 failing tests across all 3 CI platforms.
2. CI run 26890551971 execution tree showed "Run Tests" step failed on all OSes. Log extraction with `--log-failed` revealed 7 specific test failures.
3. Local reproduction confirmed all 7 tests fail on macOS, confirming cross-platform issue.
4. Git diff of commit `0335c11d` showed `preexec_fn` changed from `os.setpgrp()` to `os.setsid()`, and `_detect_interactive_prompt` gained new patterns. No changes to `_handle_timeout` body.
5. MRE probe script (spikes/debug/07-timeout-probe.py) empirically verified:
   - Probes 1-4: 2-element `communicate.side_effect` list causes `_handle_timeout` to always return generic timeout message (stdout/stderr wiped by caught TimeoutExpired).
   - Probe 5: `communicate.return_value` pattern correctly triggers interactive prompt detection.
   - Probe 6: `patch("subprocess.Popen")` does NOT affect `adapter._popen` because `_popen` is bound at constructor time.
6. Reads of `test_shell_adapter_windows_interactive.py`, `test_shell_adapter_background.py`, and `test_shell_adapter_timeout.py` confirmed all 3 failure categories share the `_popen` constructor binding root cause.

## Solution

### Root Cause
The `ShellAdapter` caches `self._popen = subprocess.Popen` at construction time. This makes the adapter impervious to global `patch("subprocess.Popen")` in tests, because the instance variable already holds a direct reference to the real function. Additionally, 4 `_handle_timeout` direct tests use a 2-element `communicate.side_effect` list containing `TimeoutExpired` as the first element—a pattern designed for `_run_subprocess`'s two-call flow—but `_handle_timeout` only calls `communicate` once, causing the exception to be caught and stdout/stderr to be wiped.

### Fix Applied (3 Test Files)
1. **`test_shell_adapter_windows_interactive.py`**: Changed `_make_timeout_process` to set `communicate.return_value` instead of `communicate.side_effect`. Updated 4 test methods to pass `return_value` tuples directly.
2. **`test_shell_adapter_background.py`**: Changed 2 tests from `patch("subprocess.Popen")` to `patch.object(adapter, '_popen')` to inject the mock into the adapter's cached reference.
3. **`test_shell_adapter_timeout.py`**: Changed `test_execute_handles_timeout_with_partial_output` from `patch("subprocess.Popen")` to `patch.object(adapter, '_popen')`.

### Production Code
The production code in `shell_adapter.py` is correct. When properly tested:
- `_handle_timeout` correctly detects interactive prompts from stderr patterns.
- `_handle_timeout` correctly preserves partial stdout/stderr for non-interactive timeouts.
- The `preexec_fn` changes (`os.setsid` instead of `os.setpgrp`) work as intended.

### Preventative Measures (Systemic)
- **Pattern to avoid:** Constructor caching of injectable function references (e.g., `self._popen = subprocess.Popen`) makes unit testing brittle because global `patch` has no effect on already-bound instance variables.
- **Recommended pattern:** Either (a) inject `Popen` as a constructor dependency with a default of `subprocess.Popen` (so tests can inject mocks at construction time), or (b) use `patch.object(adapter, '_popen')` in tests to target the specific instance.
- **Test mock pattern:** When testing methods that call `communicate` directly (like `_handle_timeout`), use `communicate.return_value` instead of a multi-element `communicate.side_effect` list, unless the flow explicitly calls `communicate` multiple times.
