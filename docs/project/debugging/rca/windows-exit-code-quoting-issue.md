# RCA: Windows Exit Code Swallowing due to Quoting in `cmd.exe` Chains

- **Status:** Resolved
- **MRE:** CI log observation of test failures on `windows-latest` runners.

## 1. Summary

Despite a previous fix for `cmd.exe` exit code propagation, unit and acceptance tests for granular failure reporting in `EXECUTE` actions continued to fail on Windows. The system incorrectly reported success (exit code 0) when a sub-command in a multi-line or chained script failed. This defeated the "fail-fast" mechanism for `EXECUTE` actions on Windows.

## 2. Investigation Summary

- **Hypothesis 1:** The `&&`/`||` chaining logic itself was flawed and did not propagate `ERRORLEVEL`. This was invalidated by a series of spikes that isolated the command generation logic from the execution environment.
- **Hypothesis 2 (Verified):** The string manipulation logic responsible for generating the Windows-specific command wrapper in `ShellAdapter._prepare_command_for_platform` failed to handle commands containing double quotes. This created a syntactically invalid command string.
- **Verification:** An inspection spike (`spikes/debug/inspect_windows_command.py`) was created to print the exact command string generated for the failing test case. It revealed that inner double quotes from the Python command (e.g., `python -c "..."`) prematurely terminated the outer `cmd /c "..."` string, corrupting the command. This syntax error caused `cmd.exe` to fail in a way that swallowed the non-zero exit code.

## 3. Root Cause

1.  **Technical (Incorrect String Escaping):** The `safe_line` generation logic in `src/teddy_executor/adapters/outbound/shell_adapter.py` did not account for commands containing double quotes (`"`). When constructing the failure-reporting clause (`... || cmd /c "echo FAILED_COMMAND: {safe_line} ..."`), the unescaped inner quotes broke the command syntax, causing `cmd.exe` to misinterpret the command chain and ultimately return a `0` exit code.
2.  **Systemic (Insufficient Cross-Platform Testing):** The initial verification spike for the first RCA ran on a non-Windows platform (`darwin`), which produced a false positive and masked the underlying issue. A more robust local testing strategy for platform-specific code is needed.

## 4. Verified Solution

The solution is to modify the `safe_line` generation to replace double quotes with single quotes before echoing the failed command. This produces a syntactically valid `cmd.exe` command string that is safe for display in an error message.

**Blueprint for `src/teddy_executor/adapters/outbound/shell_adapter.py`:**
```python
#### FIND:
                    safe_line = (
                        line.replace("(", "^(")
                        .replace(")", "^)")
                        .replace("&", "^&")
                        .replace("|", "^|")
                        .replace(">", "^>")
                        .replace("<", "^<")
                    )
#### REPLACE:
                    # THE FIX: Replace double quotes to prevent breaking the outer "..."
                    safe_line = (
                        line.replace('"', "'")
                        .replace("(", "^(")
                        .replace(")", "^)")
                        .replace("&", "^&")
                        .replace("|", "^|")
                        .replace(">", "^>")
                        .replace("<", "^<")
                    )
```

## 5. Preventative Measures

-   **Defensive String Quoting:** When generating shell command strings that will be executed inside another quoted context (like `cmd /c "..."`), all inner quotes that are part of the payload must be escaped or replaced.
-   **Platform-Specific Spike Validation:** When debugging a platform-specific issue, any verification spike must include a check to ensure it is running on the correct target platform to avoid misleading results. The high-fidelity spike `spikes/debug/validate_fix_integration.py` serves as a good template.

## 6. Recommended Regression Test

The fix is protected by the CI execution of the following tests on Windows hosts. No changes to the tests are needed, as they correctly captured the original failure.
- `tests/unit/adapters/outbound/test_shell_adapter_granular_failure.py`
- `tests/acceptance/test_execute_granular_failure.py`
