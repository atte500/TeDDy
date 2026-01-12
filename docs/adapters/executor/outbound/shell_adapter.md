# Outbound Adapter: Shell Adapter

**Status:** Refactoring
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

### `execute(command: str, cwd: Optional[str], env: Optional[Dict[str, str]])` Method Logic

The `execute` method will implement the contract defined by the `IShellExecutor` port.

1.  **Invoke Subprocess:** It will call `subprocess.run()` and pass the `cwd` and `env` parameters directly to it. The `subprocess` module handles `None` values for these parameters correctly, so no conditional logic is needed in the adapter.
    *   `command`: The command string to execute.
    *   `shell=True`: To ensure the command is interpreted by the system's shell.
    *   `capture_output=True`: To capture `stdout` and `stderr`.
    *   `text=True`: To decode `stdout` and `stderr` as text.
    *   `cwd=cwd`: The working directory for the command.
    *   `env=env`: The environment variables for the command's process.
2.  **Handle Results:** The `subprocess.run()` call returns a `CompletedProcess` object.
3.  **Create Domain Object:** The adapter will extract `stdout`, `stderr`, and `returncode` from the `CompletedProcess` object.
4.  **Return `CommandResult`:** It will instantiate and return a `CommandResult` domain object, populating it with the captured values.

```python
# Conceptual implementation
import subprocess
from typing import Dict, Optional
from teddy.core.domain import CommandResult
from teddy.core.ports.outbound import IShellExecutor

class ShellAdapter(IShellExecutor):
    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> CommandResult:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env
        )
        return CommandResult(
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode
        )
```

## 4. Rationale for No Spike

A technical spike is not required. The `subprocess` module's handling of `cwd` and `env` is a core, stable, and well-understood part of the Python standard library. There is no technical uncertainty to resolve.
