- **Status:** Verified 🟢
- **MRE:** [docs/project/debugging/mre/windows-exit-code-quoting-regression.md](/docs/project/debugging/mre/windows-exit-code-quoting-regression.md)

## 1. Summary
The `ShellAdapter` on Windows failed to report granular failure information (the `failed_command`) when a script used `exit /b`. Although the return code was correctly identified as non-zero, the failure handler was never triggered because `exit /b` terminated the entire command context immediately when invoked with `call` inside a grouped command `(...)`.

## 2. Investigation Summary
- **Hypothesis:** `exit /b` bypasses the `||` operator in `cmd.exe`.
- **Verification Spike (CI):** A diagnostic job in CI tested several permutations on a Windows Server 2025 runner.
  - `(call exit /b 1 || echo HANDLER)` -> FAILED (Handler did not run).
  - `(cmd /c "exit /b 1" || echo HANDLER)` -> SUCCESS (Handler ran).
  - `(call python ... || echo HANDLER)` -> SUCCESS (Handler ran).
- **Fail-Fast Verification:** Testing revealed that the handler must explicitly terminate with a non-zero exit code to prevent the rest of a multi-line `&&` chain from executing.

## 3. Root Cause
1.  **Technical (`cmd.exe` Context Termination):** When `exit /b` is executed within a `cmd /c` session (which the `ShellAdapter` uses) and is part of a grouped command or logical chain, it signals the current command processor to stop immediately. The `call` prefix does not isolate this behavior.
2.  **Technical (Sub-shell Survival):** Wrapping the command in `cmd /c` isolates the termination to a sub-shell, allowing the parent shell to survive, detect the non-zero exit code, and execute the `||` error handler.

## 4. Verified Solution
The solution is a "Surgical Hybrid" wrapping strategy for Windows:
- Commands starting with `exit` are wrapped in `cmd /c "{line}"`.
- All other commands continue to use the `call {line}` wrapper to avoid complex quoting issues.
- The failure handler always uses `cmd /c "echo ... & exit 1"` to ensure propagation.

**Blueprint for `src/teddy_executor/adapters/outbound/shell_adapter.py`:**
```python
# In ShellAdapter._prepare_command_for_platform, under the `sys.platform == "win32"` block:
#### FIND:
                    # We use 'call' to ensure that built-in commands like 'exit /b'
                    # do not terminate the parent shell before the || handler runs.
                    wrapped_parts.append(
                        f'(call {line} || cmd /c "echo FAILED_COMMAND: {safe_line} >&2 & exit 1")'
                    )
#### REPLACE:
                    # Surgical isolation for 'exit' commands. Using 'call' for 'exit /b'
                    # terminates the parent context; 'cmd /c' allows the parent to survive.
                    prefix = "cmd /c" if line.strip().lower().startswith("exit") else "call"
                    cmd_part = f'"{line}"' if prefix == "cmd /c" else line

                    wrapped_parts.append(
                        f'({prefix} {cmd_part} || cmd /c "echo FAILED_COMMAND: {safe_line} >&2 & exit 1")'
                    )
```

### Implementation Notes (2026-03-16)
The fix was implemented as described. Unit tests were added to `tests/unit/adapters/outbound/test_shell_adapter_windows_logic.py` to verify the surgical wrapping logic by mocking `sys.platform`.

## 5. Preventative Measures
-   **Surgical Shell Isolation:** When handling shell built-ins that modify process state (like `exit`, `set`, `cd`), evaluate if they need isolation in a sub-shell.
-   **High-Fidelity CI Spikes:** Platform-specific shell behavior (especially `cmd.exe`) must be verified on the actual target OS using isolated diagnostic jobs in CI.

## 6. Recommended Regression Test
`tests/unit/adapters/outbound/test_shell_adapter_granular_failure.py::test_windows_specific_failure_behavior`
