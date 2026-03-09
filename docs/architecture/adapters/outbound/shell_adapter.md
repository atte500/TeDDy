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

### Command Execution

The `execute` method runs the command string provided by the core. To ensure consistent behavior across platforms while supporting shell features like chaining (`&&`) and directives (`cd`), it utilizes the system shell.

1.  **CWD Validation:** It first validates that the `cwd` parameter resolves to a path within the project directory, preventing any directory traversal exploits.
2.  **Platform-Specific Execution:** It determines whether to use `shell=True` based on the platform to ensure consistent behavior. On POSIX systems, `shell=True` is always used to support features like pipes and globbing. On Windows, it uses a "Smart Router" strategy, running commands directly if they are executable files and using the shell for built-ins.
3.  **Subprocess Execution:** The adapter uses Python's `subprocess.run` to execute the command, capturing `stdout`, `stderr`, and the `return_code`.
4.  **Result Mapping:** It maps the raw results to a `ShellOutput` domain object.
5.  **Debug Mode:** If the `TEDDY_DEBUG` environment variable is set, detailed pre-execution and post-execution logs are printed to `stderr` to aid in diagnostics.
