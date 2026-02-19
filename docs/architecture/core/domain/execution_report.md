# Domain Model: ExecutionReport

This document defines the strongly-typed data structures for reporting the outcome of a plan execution. It replaces previous dictionary-based models to ensure type safety and clarity throughout the application.

## 1. Design Principles

-   **Immutability:** All report models are implemented as frozen dataclasses to prevent accidental mutation after creation.
-   **Strong Typing:** All fields use concrete types, eliminating ambiguity and enabling static analysis.
-   **Clarity:** Field names are chosen to be explicit and self-documenting.

## 2. Data Contracts

The reporting model is composed of enums for status codes and several dataclasses for structuring the report data.

### `RunStatus` (Enum)
Defines the set of possible outcomes for an entire plan execution.

**Status:** Implemented

```python
from enum import Enum

class RunStatus(str, Enum):
    """Overall status for an entire plan execution."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SKIPPED = "SKIPPED"
```

### `ActionStatus` (Enum)
Defines the set of possible outcomes for a single action within a plan.

**Status:** Implemented

```python
from enum import Enum

class ActionStatus(str, Enum):
    """Status for a single action within a plan."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"
    PENDING = "PENDING"
```

### `ActionLog`
This model captures the specific outcome of a single action within the plan.

**Status:** Implemented

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ActionLog:
    """Logs the result of a single action execution."""
    status: ActionStatus
    action_type: str
    params: dict[str, Any]
    details: Any | None = None
```

### `RunSummary`
This model captures the overall outcome of the entire plan execution.

**Status:** Implemented

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class RunSummary:
    """Summarizes the overall result of a plan execution."""
    status: RunStatus
    start_time: datetime
    end_time: datetime
    error: str | None = None
```

### `ExecutionReport`
This is the root model that aggregates all information about the plan execution.

**Status:** Implemented

```python
from dataclasses import dataclass, field
from typing import Sequence

@dataclass(frozen=True)
class ExecutionReport:
    """The comprehensive report of a plan execution."""
    run_summary: RunSummary
    plan_title: str | None = None
    action_logs: Sequence[ActionLog] = field(default_factory=list)
    validation_result: Sequence[str] | None = None
    failed_resources: dict[str, str] | None = None
```
-   `run_summary`: Contains the overall status and timing information.
-   `plan_title`: The title of the plan, extracted from the Markdown.
-   `action_logs`: A sequence of logs, one for each action attempted.
-   `validation_result`: A sequence of error messages if pre-flight validation fails.
-   `failed_resources`: A dictionary mapping file paths to their content if a file-based action (like `CREATE` or `EDIT`) fails.
