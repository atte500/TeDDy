# RCA: Windows Exit Code Swallowing in Granular Failure Reporting

- **Status:** Resolved
- **MRE:** N/A (CI Log Observation)

## 1. Summary
On Windows Server 2025, multi-line `EXECUTE` actions were reporting success (exit code 0) even when internal sub-commands failed. This broke the "fail-fast" expectation and granular failure reporting.

## 2. Investigation Summary
- **Hypothesis:** `exit /b 1` inside a parenthesized block in a `cmd /c` one-liner (used by `subprocess.run(shell=True)`) is inappropriate for process termination.
- **Verification:** Research confirmed that `exit /b` is scoped to batch contexts. In a `cmd /c` chain, it often fails to terminate the `cmd.exe` process or propagate the exit code reliably if nested in parentheses.
- **Refinement:** Investigation revealed that the Windows adapter was also missing escaping for redirection operators (`>` and `<`) and was inconsistent with POSIX by not wrapping single-line chained commands.

## 3. Root Cause
1. **Technical:** Usage of `exit /b` instead of `exit` in a non-batch shell context.
2. **Inconsistency:** Disparity between POSIX and Windows wrapping triggers (`is_multiline` vs `is_complex`).
3. **Escaping Gap:** Missing escapes for `>` and `<` which could redirect diagnostic output away from stderr.

## 4. Verified Solution
The solution is to use `exit 1` for robust termination, expand wrapping to all "complex" commands (including single-line chains), and escape redirection operators.

**Blueprint for `src/teddy_executor/adapters/outbound/shell_adapter.py`:**

```python
#### FIND:
        if sys.platform == "win32":
            # For Windows, we only wrap multiline commands if they don't look like
            # a single multiline script (e.g., using triple quotes).
            is_likely_single_script = "'''" in command or '"""' in command
            if is_multiline and not is_likely_single_script:
                # Wrap multiline commands to fail-fast on Windows.
                # We use a string and shell=True for better quote handling by subprocess.
                lines = [line.strip() for line in command.split("\n") if line.strip()]
                wrapped_parts = []
                for line in lines:
                    # Escape special characters that break cmd.exe parentheses using ^.
                    # This is critical for Python commands containing ( and ).
                    safe_line = (
                        line.replace("(", "^(")
                        .replace(")", "^)")
                        .replace("&", "^&")
                        .replace("|", "^|")
                    )
                    wrapped_parts.append(
                        f"{line} || (echo FAILED_COMMAND: {safe_line} >&2 & exit /b 1)"
                    )
                wrapped = " && ".join(wrapped_parts)
                return wrapped, True
#### REPLACE:
        if sys.platform == "win32":
            # For Windows, we wrap complex commands if they don't look like
            # a single multiline script (e.g., using triple quotes).
            is_likely_single_script = "'''" in command or '"""' in command
            if is_complex and not is_likely_single_script:
                # Wrap complex commands to fail-fast on Windows.
                lines = [line.strip() for line in command.split("\n") if line.strip()]
                wrapped_parts = []
                for line in lines:
                    # Escape special characters that break cmd.exe parentheses or redirect output.
                    safe_line = (
                        line.replace("(", "^(")
                        .replace(")", "^)")
                        .replace("&", "^&")
                        .replace("|", "^|")
                        .replace(">", "^>")
                        .replace("<", "^<")
                    )
                    wrapped_parts.append(
                        f"{line} || (echo FAILED_COMMAND: {safe_line} >&2 & exit 1)"
                    )
                wrapped = " && ".join(wrapped_parts)
                return wrapped, True
```

## 5. Preventative Measures
- **Cross-Platform Verification Spikes:** Always verify shell wrapping logic on Windows and POSIX using a simulation spike (like `spikes/debug/test_windows_wrapper_logic.py`) if native hardware is unavailable.
- **Granular CI Tests:** Maintain acceptance tests that explicitly fail internal commands to verify error propagation.

## 6. Recommended Regression Test
The fix is protected by the following existing tests (once the blueprint is applied):
- `tests/unit/adapters/outbound/test_shell_adapter_granular_failure.py`
- `tests/acceptance/test_execute_granular_failure.py`
