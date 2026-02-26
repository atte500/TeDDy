# Outbound Port: IShellExecutor

**Status:** Implemented
**Language:** Python 3.9+ (using Abstract Base Classes)
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/executor/01-walking-skeleton.md)
**Modified in:** [Structured `execute` Action](../../slices/executor/18-structured-execute-action.md)

## 1. Purpose

This port defines the interface that the application core requires for executing shell commands. By depending on this interface, the core logic remains decoupled from the specific implementation details of running a subprocess. Any adapter that can run a shell command in a specific context (working directory, environment) and capture its output can satisfy this port.

## 2. Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional
from teddy_executor.core.domain.models.shell_output import ShellOutput

class IShellExecutor(ABC):
    """
    Defines the contract for executing a shell command.
    """

    @abstractmethod
    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> ShellOutput:
        """
        Executes a shell command and returns its result.
        """
        pass
```

## 3. Method Contracts

### `execute(command: str, cwd: Optional[str], env: Optional[Dict[str, str]]) -> ShellOutput`
**Status:** Implemented

*   **Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/executor/01-walking-skeleton.md)
*   **Modified in:** [Structured `execute` Action](../../slices/executor/18-structured-execute-action.md)
*   **Description:** This method accepts a command string and optional `cwd` and `env` parameters. It executes the command within the specified context and waits for its completion, returning a structured `ShellOutput` object.
*   **Preconditions:**
    *   `command` must be a non-empty string representing a valid shell command.
    *   If provided, `cwd` must be a string representing a *relative* directory path. The adapter is responsible for validating this path.
    *   If provided, `env` must be a dictionary of string key-value pairs.
*   **Raises:**
    *   `ValueError`: If the `cwd` path is absolute or attempts to traverse outside the project directory.
*   **Postconditions:**
    *   A valid `ShellOutput` object is always returned.
    *   The method will block until the command has finished executing.
    *   If the command cannot be found, the method captures the shell's error in the `stderr` field of the `ShellOutput` and provides a non-zero `return_code`.
