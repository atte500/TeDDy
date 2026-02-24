# Inbound Port: Run Plan Use Case

**Status:** Implemented
**Language:** Python 3.9+ (using Abstract Base Classes)
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

This port defines the primary entry point for executing a plan. It represents the interface that all driving adapters (e.g., CLI, web server) will use to interact with the application core. It is responsible for orchestrating the parsing of a plan, its execution, and the generation of a final report.

## 2. Interface Definition

```python
from abc import ABC, abstractmethod
from teddy_executor.core.domain.models import ExecutionReport, Plan

class RunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(self, plan: Plan, interactive: bool) -> ExecutionReport:
        """
        Takes a parsed Plan object, executes it, and returns a report.

        Args:
            plan: The parsed Plan object to execute.
            interactive: A flag to enable/disable step-by-step user approval.
        """
        pass
```

## 3. Method Contracts

### `execute(plan: Plan, interactive: bool) -> ExecutionReport`
**Status:** Implemented

*   **Description:** This is the sole method on the port. It accepts a pre-parsed `Plan` object, orchestrates the step-by-step execution of the actions described within it, and returns a structured `ExecutionReport` domain object.
*   **Preconditions:**
    *   `plan` must be a fully parsed and valid `Plan` domain object.
*   **Postconditions:**
    *   A valid `ExecutionReport` object is returned.
    *   All actions within the plan will be evaluated and either executed, skipped, or failed, with corresponding logs in the report.
