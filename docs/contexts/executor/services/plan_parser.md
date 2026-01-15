# Application Service: PlanParser

The `PlanParser` is a single-responsibility service within the hexagonal core. Its sole purpose is to read a plan from a specified file path, validate its structure, and parse it into a structured `Plan` domain object.

## 1. Design Principles

-   **Single Responsibility:** This service only deals with parsing. It does not execute actions or interact with the user.
-   **Error Handling:** It is responsible for gracefully handling I/O errors (e.g., file not found) and parsing errors (e.g., invalid YAML, missing required fields), returning a result object or raising a specific application exception.
-   **Decoupling:** It depends on the `IFileSystemManager` outbound port to read the file, decoupling it from the concrete file system implementation.

## 2. Dependencies

-   **Outbound Ports:**
    -   `IFileSystemManager`: To read the contents of the plan file.

## 3. Public Interface

The `PlanParser` service exposes a single method.

### `parse`
Parses a plan file into a `Plan` domain object.

**Status:** Planned

```python
from pathlib import Path
from teddy_executor.core.domain.models import Plan # Assuming a Plan domain model exists

class PlanParser:
    def __init__(self, file_system_manager: IFileSystemManager):
        self._file_system_manager = file_system_manager

    def parse(self, plan_path: Path) -> Plan:
        """
        Reads and parses the specified YAML plan file.

        Args:
            plan_path: The path to the plan file.

        Returns:
            A Plan domain object representing the validated plan.

        Raises:
            PlanNotFoundError: If the file does not exist at the given path.
            InvalidPlanError: If the file content is not valid YAML or
                              if it does not conform to the expected plan structure.
        """
        pass
```

## 4. Domain Models (Input/Output)

### `Plan` (Output)
The `PlanParser` will produce a `Plan` domain object. This object will be a strongly-typed dataclass representation of the YAML file.

```python
from dataclasses import dataclass
from typing import Sequence, Any

@dataclass(frozen=True)
class ActionData:
    """Represents a single action from the plan."""
    type: str
    params: dict[str, Any]

@dataclass(frozen=True)
class Plan:
    """Represents a parsed and validated execution plan."""
    actions: Sequence[ActionData]
```
