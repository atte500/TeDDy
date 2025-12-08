# Outbound Port: Shell Executor

**Language:** Python 3.9+ (using Abstract Base Classes)
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

This port defines the interface that the application core requires for executing shell commands. By depending on this interface, the core logic remains decoupled from the specific implementation details of running a subprocess (e.g., Python's `subprocess` module, `os.system`, etc.). Any adapter that can run a shell command and capture its output can satisfy this port.

## 2. Interface Definition

```python
from abc import ABC, abstractmethod
from teddy.core.domain import CommandResult

class ShellExecutor(ABC):
    """
    Defines the contract for executing a shell command.
    """

    @abstractmethod
    def run(self, command: str) -> CommandResult:
        """
        Executes a shell command and returns its result.
        """
        pass
```

## 3. Method Contracts

### `run(command: str) -> CommandResult`

*   **Status:** `Defined`
*   **Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)
*   **Description:** This method accepts a single string representing a shell command, executes it, and waits for its completion. It then returns a structured `CommandResult` object containing the captured stdout, stderr, and the command's exit code.
*   **Preconditions:**
    *   `command` must be a non-empty string representing a valid shell command.
*   **Postconditions:**
    *   A valid `CommandResult` object is always returned.
    *   The method will block until the command has finished executing.
    *   If the command cannot be found (e.g., `nonexistentcommand123`), the method does not raise an exception. Instead, it captures the shell's error message in the `stderr` field of the returned `CommandResult` and provides a non-zero `return_code`.
