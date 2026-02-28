# Application Service: ExecutionOrchestrator

The `ExecutionOrchestrator` is the primary application service in the hexagonal core for running a plan. It acts as the use case controller, coordinating other services and ports to execute a plan from start to finish and generate a comprehensive report.

## 1. Design Principles

-   **Use Case Controller:** This service directly implements the `run_plan` use case.
-   **Coordination, Not Creation:** Its role is to orchestrate calls to other single-responsibility services (`PlanParser`, `ActionDispatcher`). It does not contain complex business logic itself.
-   **State Management:** It manages the state of the execution run, collecting `ActionLog` objects and building the final `ExecutionReport`.
-   **Port-driven Interaction:** All side effects (user interaction, file I/O) are delegated through outbound ports, keeping the orchestrator's logic pure and testable.

## 2. Dependencies

-   **Application Services:**
    -   `ActionDispatcher`: To execute each action in the plan.
-   **Outbound Ports:**
    -   `IUserInteractor`: To prompt the user for step-by-step approval during interactive execution.
    -   `IFileSystemManager`: For contextual file reading.

## 3. Public Interface

The `ExecutionOrchestrator` service exposes a single method, fulfilling the `IRunPlanUseCase` inbound port.

### `execute`
Orchestrates the execution of a pre-parsed plan, returning a final report.

**Status:** Implemented

```python
from teddy_executor.core.domain.models import ExecutionReport, Plan
from teddy_executor.core.ports.outbound import IUserInteractor, IFileSystemManager
from teddy_executor.core.services import ActionDispatcher

class ExecutionOrchestrator:
    def __init__(
        self,
        action_dispatcher: ActionDispatcher,
        user_interactor: IUserInteractor,
        file_system_manager: IFileSystemManager,
    ):
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor
        self._file_system_manager = file_system_manager

    def execute(self, plan: Plan, interactive: bool) -> ExecutionReport:
        """
        Coordinates the execution of a Plan.

        1.  Loops through each action in the plan.
        2.  Checks for previous failures. If any action has failed (triggering the `halt_execution` flag), subsequent actions are automatically skipped to prevent cascading failures, and `IUserInteractor.notify_skipped_action` is called to warn the user.
        3.  If in interactive mode, calls the `IUserInteractor.confirm_action` method, passing the full `ActionData` object and a descriptive prompt string to get the user's approval.
            - **Special Case:** The approval prompt is automatically skipped for `chat_with_user` actions to provide a more fluid user experience.
        4.  If approved (or not in interactive mode), calls the ActionDispatcher.
        5.  Collects the ActionLog from the dispatcher.
        6.  Builds and returns the final ExecutionReport.

        Args:
            plan: The parsed Plan object.
            interactive: A flag to enable/disable step-by-step user approval.

        Returns:
            An ExecutionReport summarizing the entire run.
        """
        pass
```

## 4. Domain Models (Input/Output)

-   **Input:** `plan: Plan`, `interactive: bool`
-   **Output:** `ExecutionReport` (from `execution_report.md`)
