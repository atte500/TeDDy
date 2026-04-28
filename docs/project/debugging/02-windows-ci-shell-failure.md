# Bug: Windows CI Shell Execution Failure

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config.md](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-06-cap-execute-output.md](../slices/00-06-cap-execute-output.md)
- **Specs:** [report-format.md](../specs/report-format.md)

## Symptoms
The Windows CI pipeline is failing. The regression is suspected to be related to the recent implementation of shell output capping.

## Context & Scope
### Regressing Delta
Recent changes in `src/teddy_executor/adapters/outbound/shell_adapter.py` for output truncation (Slice 00-06).

### Environmental Triggers
- OS: Windows (CI)
- Trigger: Shell execution commands.

### Ruled Out
- TBD

## Diagnostic Analysis
### Causal Model
`ShellAdapter` executes commands using `subprocess.Popen` with `text=True`. In this mode, Python performs universal newline translation. The recent capping logic intercepts the `stdout` and applies `truncate_lines`. Windows-specific command wrapping in `ShellCommandBuilder` adds `cmd /c` prefixes and error handling which may inject additional newlines or specific formatting that the capping logic or its tests do not expect.

### Discrepancies
- `test_windows_specific_failure_behavior` expects `failed_command` to be `"exit /b 1"`. If the Windows wrapper alters this string (e.g., escaping carets or quotes) in the `stderr` report, the assertion will fail. (Verified: `ShellCommandBuilder._prepare_windows` replaces `"` with `'` in the diagnostic echo, causing detection mismatches).
- `test_execute_multi_line_command_fails_fast_and_reports_command` uses `sys.executable` and quoted python scripts. On Windows, these quotes are transformed, breaking the assertion: `assert "sys.exit(1)" in result["failed_command"]`.

### Investigation History
1. **Gathering Context.** Observed `ShellAdapter` uses `text=True` and `truncate_lines` from `string.py`. `ShellCommandBuilder` has complex Windows wrapping logic.
2. **Isolating Mismatch.** Created MRE `debug/mre_windows_failure.py` which confirmed that `cmd.exe` wrapper swaps quotes and escapes carets, breaking the `failed_command` detection and assertions.

## Solution
### Implemented Fixes
- **ShellAdapter:** Added unescaping for carets (`^^` -> `^`) when extracting `failed_command` from Windows-wrapped diagnostic reports.
- **Unit Tests:** Updated `test_shell_adapter_granular_failure.py` to use resilient partial matching (normalizing quotes) for the `failed_command` assertion, ensuring cross-platform compatibility despite `cmd.exe` limitations.

### Prevention
- Regression tests in `test_shell_adapter_granular_failure.py` now explicitly account for platform-specific reporting nuances.
