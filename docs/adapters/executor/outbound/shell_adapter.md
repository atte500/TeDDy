# Outbound Adapter: Shell Adapter

**Status:** Implemented
**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The `ShellAdapter` is a "driven" adapter that provides the concrete implementation for running shell commands. It acts as the bridge between the application's core logic and the operating system's shell.

## 2. Implemented Ports

*   **Implements Outbound Port:** [`ShellExecutor`](../../core/ports/outbound/shell_executor.md)

## 3. Implementation Notes

*   **Technology:** The adapter will be implemented using Python's built-in `subprocess` module, which is the modern and recommended way to handle external commands.
*   **Entry Point:** The class `ShellAdapter` will be located in `src/teddy/adapters/outbound/shell_adapter.py`.

### `run(command: str)` Method Logic

The `run` method will implement the contract defined by the `ShellExecutor` port.

1.  **Invoke Subprocess:** It will call `subprocess.run()` with the following key arguments:
    *   `command`: The command string to execute.
    *   `shell=True`: To ensure the command is interpreted by the system's shell.
    *   `capture_output=True`: To capture `stdout` and `stderr`.
    *   `text=True`: To decode `stdout` and `stderr` as text.
2.  **Handle Results:** The `subprocess.run()` call returns a `CompletedProcess` object.
3.  **Create Domain Object:** The adapter will extract `stdout`, `stderr`, and `returncode` from the `CompletedProcess` object.
4.  **Return `CommandResult`:** It will instantiate and return a `CommandResult` domain object, populating it with the captured values. This fulfills the port's contract.

```python
# Conceptual implementation
import subprocess
from teddy.core.domain import CommandResult
from teddy.core.ports.outbound import ShellExecutor

class ShellAdapter(ShellExecutor):
    def run(self, command: str) -> CommandResult:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        return CommandResult(
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode
        )
```

## 4. Rationale for No Spike

Similar to the CLI adapter, a technical spike is not required here. The `subprocess` module is a core, stable, and well-understood part of the Python standard library. There is no technical uncertainty to resolve regarding its behavior for this use case.
