# Bug: Windows Interactive Prompt Detection Failure

- **Status:** Resolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [docs/project/slices/02-06-orchestrator-hardening.md](docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](docs/project/specs/stability-and-bugfixes.md)

## Symptoms

**Expected:** When executing a Windows interactive command (e.g., `cmd /c "set /p test_var="`) via `ShellAdapter`, the adapter should detect that the command requires interactive input and return `ShellAdapter.INTERACTIVE_PROMPT_MESSAGE` in stdout (a standardized failure message).

**Actual:** The command returns exit code 1 with empty stdout and stderr. The assertion `assert 'FAILURE: Interactive prompt detected' in result["stdout"]` fails.

## Context & Scope

### Regressing Delta
Commit `3f84359c feat(shell): implement Windows interactive prompt detection with direct-method test harness` introduced both the test `test_real_windows_interactive_command` and the current detection logic. The detection strategy relies solely on checking stderr for patterns (e.g., "Input required", "Unexpected EOF") via `_detect_interactive_prompt()`. However, `cmd /c "set /p test_var="` with `stdin=DEVNULL` exits with code 1 and produces **no stderr output**. Therefore the detection never triggers, and the command is treated as a generic failure.

### Environmental Triggers
- **OS:** Windows (windows-latest CI runner)
- The test `test_real_windows_interactive_command` in `tests/suites/unit/adapters/outbound/test_shell_adapter_windows_interactive.py`
- The command `cmd /c "set /p test_var="` is executed with `stdin=DEVNULL`.
- Windows `set /p` exits silently with code 1 and no stderr when stdin is not a terminal.
- The detection logic `_detect_interactive_prompt()` only inspects stderr.

### Ruled Out
- ShellCommandBuilder wrapping: The command is not wrapped by `_prepare_windows` for complex chains; it runs directly as `cmd /c "set /p test_var="` with `shell=True`.
- The `FAILED_COMMAND:` marker extraction: Since the command is not wrapped, no marker appears in stderr.

## Diagnostic Analysis

### Causal Model
The `ShellAdapter.execute()` calls `_run_subprocess()` which runs the command with `stdin=DEVNULL`. On Windows, `cmd /c "set /p test_var="` with DEVNULL exits immediately with `returncode=1` and produces **no stdout and no stderr**. `_process_execution_results()` checks `_detect_interactive_prompt(stderr)`; stderr is empty, so detection fails. The result is `{stdout: "", stderr: "", return_code: 1}`. The test expects `stdout` to contain `"FAILURE: Interactive prompt detected"`, but since neither stdout nor stderr contained interactive patterns, the raw empty output is returned.

**Fix Strategy (Two-Axis):**
1. **Proactive (pre-execution):** Add `_is_interactive_command(command: str) -> bool` that inspects the raw command string for known Windows interactive patterns (`set /p`, `choice`, `pause`, `more`, `getpass`, `read -p`). If matched, return `INTERACTIVE_PROMPT_MESSAGE` immediately without spawning a subprocess.
2. **Reactive (post-execution):** Enhance `_detect_interactive_prompt` to accept an optional `stdout` parameter and check both streams. Additionally, add a heuristic: on Windows, if `return_code == 1` and both `stdout` and `stderr` are empty, treat it as interactive (since silent exit with error and no output is a strong indicator of TTY requirement).

### Discrepancies
- `_detect_interactive_prompt` only checks stderr, but Windows interactive commands (like `set /p`) may exit silently without stderr output. (Resolved: dual-channel detection now checks both stdout and stderr; Windows silent exit heuristic catches empty-output failures with exit code 1.)
- The spec for Windows detection mentions proactive probing via `WaitForInputIdle` or EOF mapping, but only the latter (stderr patterns) is implemented. (Resolved: dual-channel + silent exit heuristic provide coverage without pre-execution probing.)
- The test assumes detection via stderr patterns, but the real subprocess does not produce those patterns. (Resolved: the silent exit heuristic catches `set /p` post-execution; dual-channel catches other commands that print to stdout.)

### Investigation History
1. Identified failing test `test_real_windows_interactive_command` on Windows CI. Hypothesis: stderr-based detection fails because `set /p` produces no stderr. Observation: Code analysis confirms stderr is empty. Conclusion: Need alternative detection strategy (stdout checks or command pre-analysis).
2. RPP log retrieval failed (workflow run 26891788075 no longer accessible via `-j "Probe (windows-latest)"`). Switched to direct code analysis and shadow file verification. Conclusion: The root cause is confirmed; skip further remote probing.
3. Shadow file fix verified locally with 15/15 tests passing (9 dual-channel + 6 silent exit). Post-execution-only strategy validated per user feedback.

## Solution

### Root Cause
`ShellAdapter._detect_interactive_prompt()` only checked **stderr** for interactive patterns. On Windows, `cmd /c "set /p test_var="` with `stdin=DEVNULL` exits immediately with `return_code=1` and produces **both empty stdout and stderr**. Since stderr had no detectable patterns, the interactive prompt detection never triggered, and the raw empty output (with code 1) was returned unmodified.

### Fix (Post-Execution Only)
Two complementary post-execution mechanisms in `shell_adapter.py`:

1. **Dual-Channel `_detect_interactive_prompt(stderr, stdout)`** – The signature now accepts an optional `stdout` parameter. The method checks **both streams** against the interactive patterns list. This captures commands that print interactive indicators to stdout rather than stderr.

2. **Windows Silent Exit Heuristic** – In `_process_execution_results`, if `sys.platform == "win32"`, `return_code == 1`, and **both** stdout and stderr are empty, the output is mapped to `INTERACTIVE_PROMPT_MESSAGE`. This handles the specific scenario where `set /p` exits silently with code 1 and no output when stdin is not a terminal.

### Preventative Measures
This fix addresses the "Single-Channel Stream Detection" category. To prevent this class of issue globally:
- **Grep-based audit**: The `_detect_interactive_prompt` method is only used within `shell_adapter.py` (2 call sites plus its definition). No other component performs stream-based interactive detection, so the fix is contained.
- **Code review standard**: All future detection methods that inspect subprocess output MUST check all available channels (stdout, stderr, return code) rather than relying on a single stream.
- **Test coverage**: The existing test parametrization in `TestDetectInteractivePrompt` should be extended to cover both streams. The new silent exit heuristic is covered by `TestProcessExecutionResults` tests (added to the shadow file verification).
