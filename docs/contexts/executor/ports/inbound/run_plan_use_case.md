# Inbound Port: Run Plan Use Case

**Status:** Implemented
**Language:** Python 3.9+ (using Abstract Base Classes)
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

This port defines the primary entry point for executing a plan. It represents the interface that all driving adapters (e.g., CLI, web server) will use to interact with the application core. It is responsible for orchestrating the parsing of a plan, its execution, and the generation of a final report.

## 2. Interface Definition

```python
from abc import ABC, abstractmethod
from teddy.core.domain import ExecutionReport

class RunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(self, plan_content: str, auto_approve: bool = False) -> ExecutionReport:
        """
        Takes raw plan content, executes it, and returns a report.
        """
        pass
```

## 3. Method Contracts

### `execute(plan_content: str, auto_approve: bool = False) -> ExecutionReport`
**Status:** Implemented

*   **Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)
*   **Description:** This is the sole method on the port. It accepts a string of raw YAML content, orchestrates the full execution of the plan described in the content, and returns a structured `ExecutionReport` domain object.
*   **Preconditions:**
    *   `plan_content` must be a string. For the Walking Skeleton, it is expected to be valid YAML representing a list of actions.
*   **Postconditions:**
    *   A valid `ExecutionReport` object is returned.
    *   If `plan_content` is syntactically invalid, the returned `ExecutionReport` will contain a single `ActionResult` with a `FAILURE` status and an error message detailing the parsing failure.
    *   If the plan is valid, all actions within the plan will be attempted, and a corresponding `ActionResult` will be present in the final report for each.
