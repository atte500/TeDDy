# Inbound Port: Run Plan Use Case

**Status:** Implemented
**Language:** Python 3.9+ (using Abstract Base Classes)

## 1. Purpose

This port defines the primary entry point for executing a plan. It represents the interface that all driving adapters (e.g., CLI, web server) will use to interact with the application core. It is responsible for orchestrating the parsing of a plan, its execution, and the generation of a final report.

## 2. Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Optional
from teddy_executor.core.domain.models import ExecutionReport, Plan

class IRunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> ExecutionReport:
        """
        Executes a plan and returns a report.

        Args:
            plan: An already parsed Plan object.
            plan_content: Raw Markdown content of a plan.
            plan_path: Path to a plan file on disk.
            interactive: A flag to enable/disable step-by-step user approval.
            message: Optional user instruction to include in the report.
        """
        pass

    @abstractmethod
    def resume(
        self,
        session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """
        Intelligently resumes the session based on its state.

        Args:
            session_name: The name of the session to resume.
            interactive: Whether to run in interactive mode.
            message: Optional user instruction to bridge to the next turn.
        """
        pass
```

## 3. Method Contracts

### `execute(...) -> ExecutionReport`
**Status:** Implemented

*   **Description:** Orchestrates the step-by-step execution of a plan and returns a structured `ExecutionReport` domain object.

### `resume(...) -> ExecutionReport`
**Status:** Implemented

*   **Description:** Intelligently resumes the session based on its state, triggering planning or execution as needed.
*   **Preconditions:**
    *   `plan` must be a fully parsed and valid `Plan` domain object.
*   **Postconditions:**
    *   A valid `ExecutionReport` object is returned.
    *   All actions within the plan will be evaluated and either executed, skipped, or failed, with corresponding logs in the report.
