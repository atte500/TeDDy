- **Status:** Resolved
- **MRE:** [docs/project/debugging/mre/windows-exit-code-quoting-regression.md](/docs/project/debugging/mre/windows-exit-code-quoting-regression.md)

## 1. Summary
A regression occurred where a fix for a Windows `cmd.exe` exit code propagation issue proved ineffective, causing CI builds on `windows-latest` runners to fail. The `ShellAdapter` continued to incorrectly report success (exit code 0) for multi-line `EXECUTE` commands where an intermediate line failed. This defeated the "fail-fast" mechanism on Windows.

## 2. Investigation Summary
- **Initial Hypothesis:** The problem was related to how double quotes were handled in the command wrapper, causing a syntax error. This was based on a previous, flawed RCA.
- **Verification Spike 1 (Initial Failure):** A CI-based spike was used to test command execution directly on a Windows runner. The results were surprising:
  - A single failing command with quotes, wrapped in `... || handler`, **did** propagate its exit code correctly.
  - A multi-line chain of these wrapped commands, joined by `&&`, **did not** propagate the exit code and returned `0`.
- **Root Cause Hypothesis (Verified):** The issue is not quoting, but `cmd.exe`'s operator precedence. The `&&` operator has higher precedence than `||`. Without explicit grouping, `cmd.exe` misinterprets the logic of the command chain, leading to the swallowed exit code.
- **Verification Spike 2 (Solution Validation):** The CI spike was modified to test a proposed fix: wrapping each `command || handler` pair in parentheses `(...)`. This experiment was successful and proved that the parenthesis grouping forces the correct order of operations, resolving the bug.

## 3. Root Cause
1.  **Technical (Incorrect Command Chaining):** The `ShellAdapter`'s Windows-specific logic constructs multi-line commands by joining individually wrapped `command || handler` lines with the `&&` operator. Due to `cmd.exe`'s operator precedence rules, `&&` binds more tightly than `||`. This caused the command chain to be parsed incorrectly, for example `line1 || handler1 && line2 || handler2` was interpreted as `line1 || (handler1 && line2) || handler2`, which breaks the fail-fast logic when `line2` fails.
2.  **Systemic (Incomplete Initial Analysis):** The previous RCA focused narrowly on a quoting issue, which was a red herring. The initial verification spike was not comprehensive enough to test the interaction between the `||` wrapper and the `&&` joiner, leading to an incorrect conclusion and a failed fix.

## 4. Verified Solution
The solution is to wrap each `command || handler` segment in parentheses `(...)` before joining them with `&&`. This explicitly enforces the correct order of operations for `cmd.exe`.

**Blueprint for `src/teddy_executor/adapters/outbound/shell_adapter.py`:**
```python
# In ShellAdapter._prepare_command_for_platform, under the `sys.platform == "win32"` block:
#### FIND:
                    wrapped_parts.append(
                        f'{line} || cmd /c "echo FAILED_COMMAND: {safe_line} >&2 & exit 1"'
                    )
                wrapped = " && ".join(wrapped_parts)
#### REPLACE:
                    # THE FIX: Group each command with its error handler in parentheses
                    # to enforce correct operator precedence for cmd.exe.
                    wrapped_parts.append(
                        f'({line} || cmd /c "echo FAILED_COMMAND: {safe_line} >&2 & exit 1")'
                    )
                wrapped = " && ".join(wrapped_parts)
```

## 5. Preventative Measures
-   **Command-Line Precedence Awareness:** When constructing complex, chained shell commands programmatically, always be aware of operator precedence rules (`&&`, `||`, `|`) for the target shell (`bash`, `cmd.exe`, etc.). Use explicit grouping (e.g., parentheses in `cmd.exe`, subshells `(...)` or command groups `{...}` in bash) to ensure logical correctness.
-   **Comprehensive Verification Spikes:** Diagnostic spikes for shell behavior must test not only individual components of a command but also their composition. A test for `A || B` is insufficient if the production code uses `(A || B) && (C || D)`.

## 6. Recommended Regression Test
The following tests protect this fix:
- `tests/unit/adapters/outbound/test_shell_adapter_windows_logic.py::test_windows_command_wrapping_includes_parentheses`
- `tests/unit/adapters/outbound/test_shell_adapter_granular_failure.py::test_windows_specific_failure_behavior`
- `tests/acceptance/test_execute_granular_failure.py::test_execute_reports_specific_failing_command_in_multiline_block`

## 7. Implementation Notes
Implemented on 2026-03-16. Each command segment on Windows is now wrapped in parentheses: `(command || handler) && (next_command || handler)`. This forces `cmd.exe` to evaluate the OR condition before the AND condition, ensuring the process terminates immediately on failure.
