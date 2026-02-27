# Outbound Adapter: Shell Adapter

**Status:** Implemented
**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/executor/01-walking-skeleton.md)
**Modified in:** [Structured `execute` Action](../../slices/executor/18-structured-execute-action.md)

## 1. Purpose

The `ShellAdapter` is a "driven" adapter that provides the concrete implementation for running shell commands. It acts as the bridge between the application's core logic and the operating system's shell, handling execution context like working directory and environment variables.

## 2. Implemented Ports

*   **Implements Outbound Port:** [`IShellExecutor`](../../contexts/executor/ports/outbound/shell_executor.md)

## 3. Implementation Notes

*   **Technology:** The adapter will be implemented using Python's built-in `subprocess` module.
*   **Entry Point:** The class `ShellAdapter` will be located in `src/teddy_executor/adapters/outbound/shell_adapter.py`.

### Sequential Multi-Command Runner

The `execute` method implements a **Sequential Multi-Command Runner** strategy to ensure consistent "halt-on-error" behavior and context persistence across platforms.

1.  **CWD Validation:** It first validates the `cwd` parameter to ensure it resolves to a path within the project directory, preventing directory traversal.
2.  **Command Decomposition:** Multi-line scripts and `&&` chains are decomposed into atomic commands using a robust regex that respects quoted strings. This prevents breaking complex commands (e.g., Python one-liners with newlines).
3.  **Context Persistence:** The adapter intercepts directives that alter the execution environment (`cd`, `export`, `set`) and applies them to the persistent Python-managed context for subsequent atomic steps.
4.  **Platform-Specific Execution:**
    *   **On POSIX (Linux/macOS):** Each atomic command uses `shell=True`. This enables full, standard shell functionality (globbing, pipes, etc.) while allowing Python to manage the execution flow.
    *   **On Windows:** Each atomic command uses the "Smart Router" strategy (switching between `shell=True/False` based on `shutil.which`).
5.  **Halt on Error:** If any atomic command returns a non-zero exit code, execution stops immediately. The adapter returns the accumulated `stdout` and `stderr` and the failure code.
6.  **Result Mapping:** The adapter captures results and maps them to a `ShellOutput` domain object.
7.  **Debug Mode:** If `TEDDY_DEBUG` is set, detailed logs are printed to `stderr`.

### Private Helpers

- `_decompose_command(command: str) -> List[str]`: Splits the input string into atomic commands while respecting quotes.
- `_handle_directives(cmd: str, current_cwd: str, current_env: Dict[str, str]) -> str`: Intercepts context-altering commands and updates the execution context.
