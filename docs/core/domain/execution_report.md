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

**Status:** Implemented

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# Note: The 'TeddyProject' field was removed in the as-built implementation
# in favor of a simpler model. This documentation reflects the current code.
@dataclass(frozen=True)
class RunSummary:
    """Summarizes the overall result of a plan execution."""
    status: Literal["SUCCESS", "FAILURE"]
    start_time: datetime
    end_time: datetime
    error: str | None = None
```

### `ActionLog`
This model captures the specific outcome of a single action within the plan.

**Status:** Implemented

```python
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class ActionLog:
    """Logs the result of a single action execution."""
    status: Literal["SUCCESS", "FAILURE", "SKIPPED"]
    action_type: str
    params: dict[str, Any]
    description: str | None = None  # The user-provided description from the plan.
    details: Any | None = None
```

### `ExecutionReport`
This is the root model that aggregates the run summary and all individual action logs.

**Status:** Implemented

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
