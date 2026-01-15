# Domain Model: ExecutionReport

This document defines the strongly-typed data structures for reporting the outcome of a plan execution. It replaces previous dictionary-based models to ensure type safety and clarity throughout the application.

## 1. Design Principles

-   **Immutability:** All report models are implemented as frozen dataclasses to prevent accidental mutation after creation.
-   **Strong Typing:** All fields use concrete types, eliminating ambiguity and enabling static analysis.
-   **Clarity:** Field names are chosen to be explicit and self-documenting.

## 2. Data Contracts

The reporting model is composed of three main dataclasses: `RunSummary`, `ActionLog`, and the top-level `ExecutionReport`.

### `RunSummary`
This model captures the overall outcome of the entire plan execution.

**Status:** Planned

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from teddy_executor.core.domain.models import TeddyProject

@dataclass(frozen=True)
class RunSummary:
    """Summarizes the overall result of a plan execution."""
    status: Literal["SUCCESS", "FAILURE", "SKIPPED"]
    start_time: datetime
    end_time: datetime
    project: TeddyProject
    # Optional field for a high-level error message if the entire run fails early
    # (e.g., plan parsing error).
    error: str | None = None
```

### `ActionLog`
This model captures the specific outcome of a single action within the plan.

**Status:** Planned

```python
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class ActionLog:
    """Logs the result of a single action execution."""
    status: Literal["SUCCESS", "FAILURE", "SKIPPED", "PENDING"]
    action_type: str
    params: dict[str, Any]
    # Optional field for detailed error messages or output from the action.
    details: str | None = None
```

### `ExecutionReport`
This is the root model that aggregates the run summary and all individual action logs.

**Status:** Planned

```python
from dataclasses import dataclass, field
from typing import Sequence

# Assuming RunSummary and ActionLog are defined in the same module
# from .run_summary import RunSummary
# from .action_log import ActionLog

@dataclass(frozen=True)
class ExecutionReport:
    """The comprehensive report of a plan execution."""
    run_summary: RunSummary
    action_logs: Sequence[ActionLog] = field(default_factory=list)
```
