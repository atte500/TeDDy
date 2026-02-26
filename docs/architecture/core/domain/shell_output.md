# Component: ShellOutput

- **Type:** Domain Model (DTO)
- **Context:** [Core Domain Model & Ubiquitous Language](/docs/architecture/core/domain_model.md)

## 1. Description

`ShellOutput` is a strictly-typed `TypedDict` that serves as the standardized data transfer object (DTO) for the results of any shell command executed via the `IShellExecutor` port. It replaced the legacy `CommandResult` dataclass to improve type safety and align with modern Python practices.

## 2. Public Contract (DTO)

The `ShellOutput` is a dictionary with the following structure:

```python
from typing import TypedDict

class ShellOutput(TypedDict):
    """
    A strictly-typed dictionary representing the result of a shell command execution.
    """
    stdout: str
    stderr: str
    return_code: int
```

### Fields
- **`stdout` (str):** The standard output captured from the command.
- **`stderr` (str):** The standard error captured from the command.
- **`return_code` (int):** The integer exit code of the command. A value of `0` typically indicates success.
