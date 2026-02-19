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

### Cross-Platform Execution Strategy

The `execute` method implements a cross-platform strategy to handle the differences between POSIX (Linux/macOS) and Windows shells.

1.  **CWD Validation:** It first validates the `cwd` parameter to ensure it resolves to a path within the project directory, preventing directory traversal.
2.  **Environment Merging:** It merges any provided `env` variables with the current process's environment.
3.  **Platform-Specific Execution:**
    *   **On POSIX (Linux/macOS):** The adapter uses `shell=True` and passes the raw command string to `subprocess.run`. This enables full, standard shell functionality, including globbing (`*`), pipes (`|`), and environment variable expansion (`$VAR`). This is considered safe within the TeDDy workflow because every command execution must be explicitly approved by the user in interactive mode.
    *   **On Windows:** The adapter uses a "Smart Router" strategy to avoid common quoting and path issues. It inspects the command to determine if it's a standalone executable (e.g., `git.exe`) or a shell built-in (e.g., `dir`).
        *   If it's an executable, it runs the command with `shell=False`.
        *   If it's a shell built-in, it runs the command with `shell=True`.
4.  **Result Mapping:** The adapter captures the `stdout`, `stderr`, and `returncode` from the executed process and maps them to a `CommandResult` domain object.
5.  **Debug Mode:** If the `TEDDY_DEBUG` environment variable is set, the adapter will print detailed logs about the execution process to `stderr`, aiding in diagnostics.
