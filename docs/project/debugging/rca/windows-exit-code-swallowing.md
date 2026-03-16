# RCA: Windows Exit Code Swallowing in Granular Failure Reporting

- **Status:** Resolved
- **MRE:** N/A (CI Log Observation)

## 1. Summary
On Windows Server 2025, multi-line and chained `EXECUTE` actions were reporting success (exit code 0) even when internal sub-commands failed. This broke the "fail-fast" expectation. An initial fix attempted to replace `exit /b 1` with `exit 1` inside parentheses `(...)`, but the CI suite continued to fail because the exit code was still swallowed by `cmd.exe`.

## 2. Investigation Summary
- **Hypothesis 1:** `exit /b 1` was the wrong command to terminate `cmd.exe`. (Verified in previous RCA, but insufficient).
- **Hypothesis 2 (The True Cause):** `cmd.exe` has parsing bugs in single-command mode (`cmd /c`) when `exit 1` is executed inside a grouped parenthesis block `(echo ... & exit 1)`. The implicit `&` operator or the block context prevents the `1` from propagating to the parent process.
- **Verification:** We researched `cmd.exe` exit code bugs and deduced that removing parentheses entirely avoids this edge case. Instead of `cmd1 || (echo ... & exit 1)`, we can spawn an inner `cmd /c` process: `cmd1 || cmd /c "echo ... & exit 1"`. The inner shell reliably exits with 1, halting the outer `&&` chain.
- **Secondary Discovery:** The integration test `test_shell_adapter_preserves_parent_environment` failed on Windows because `cmd.exe` `echo` commands append a trailing space when followed by `&&`.

## 3. Root Cause
1. **Technical (`cmd.exe` bug):** Usage of `exit 1` inside parenthesis groups `(...)` within a `cmd /c` single-line script causes `cmd.exe` to swallow the exit code.
2. **Test Flaw:** An environment integration test did not strip the `stdout` line before comparing it, exposing a classic `echo` trailing whitespace bug.

## 4. Verified Solution
The solution replaces the parenthesis block with a robust inner `cmd /c` call, which bypasses parsing ambiguities.

**Blueprint for `src/teddy_executor/adapters/outbound/shell_adapter.py`:**

```python
#### FIND:
                    wrapped_parts.append(
                        f"{line} || (echo FAILED_COMMAND: {safe_line} >&2 & exit 1)"
                    )
#### REPLACE:
                    wrapped_parts.append(
                        f"{line} || cmd /c \"echo FAILED_COMMAND: {safe_line} >&2 & exit 1\""
                    )
```

**Blueprint for `tests/integration/adapters/outbound/test_shell_adapter.py`:**

```python
#### FIND:
        assert result["stdout"].splitlines()[1] == "custom_value"
#### REPLACE:
        assert result["stdout"].splitlines()[1].strip() == "custom_value"
```

## 5. Preventative Measures
- **Cross-Platform Verification Spikes:** When developing fixes for `cmd.exe` without native access, write spikes that test the specific logical boundaries (e.g., quotes, parentheses, chaining) as string generation, and research known `cmd.exe` quirks.
- **Test Output Sanitization:** Always use `.strip()` when asserting exact string matches against shell `stdout`, particularly on Windows.

## 6. Recommended Regression Test
The fix is protected by the CI execution of the following tests on Windows hosts:
- `tests/unit/adapters/outbound/test_shell_adapter_granular_failure.py`
- `tests/acceptance/test_execute_granular_failure.py`
- `tests/integration/adapters/outbound/test_shell_adapter.py`
