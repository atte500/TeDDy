# Application Service: ExecutionOrchestrator

The `ExecutionOrchestrator` is the primary application service in the hexagonal core for running a plan. It acts as the use case controller, coordinating other services and ports to execute a plan from start to finish and generate a comprehensive report.

## 1. Design Principles

-   **Use Case Controller:** This service directly implements the `run_plan` use case.
-   **Coordination, Not Creation:** Its role is to orchestrate calls to other single-responsibility services (`PlanParser`, `ActionDispatcher`). It does not contain complex business logic itself.
-   **State Management:** It manages the state of the execution run, collecting `ActionLog` objects and building the final `ExecutionReport`.
-   **Port-driven Interaction:** All side effects (user interaction, file I/O) are delegated through outbound ports, keeping the orchestrator's logic pure and testable.

## 2. Dependencies

-   **Application Services:**
    -   `PlanParser`: To load and parse the plan.
    -   `ActionDispatcher`: To execute each action in the plan.
-   **Outbound Ports:**
    -   `IUserInteractor`: To prompt the user for step-by-step approval during interactive execution.

## 3. Public Interface

The `ExecutionOrchestrator` service exposes a single method, fulfilling the `IRunPlanUseCase` inbound port.

### `execute`
Orchestrates the parsing and execution of a plan, returning a final report.

**Status:** Implemented

```python
from teddy_executor.core.domain.models import ExecutionReport
from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.core.services import PlanParser, ActionDispatcher

class ExecutionOrchestrator:
    def __init__(
        self,
        plan_parser: PlanParser,
        action_dispatcher: ActionDispatcher,
        user_interactor: IUserInteractor,
    ):
        self._plan_parser = plan_parser
        self._action_dispatcher = action_dispatcher
        self._user_interactor = user_interactor

    def execute(self, plan_content: str, interactive: bool) -> ExecutionReport:
        """
        Coordinates the end-to-end execution of a plan.

        1.  Calls the PlanParser to load the plan from a string.
        2.  Loops through each action in the plan.
        3.  If in interactive mode, calls the `IUserInteractor.confirm_action` method, passing the full `Action` object and a descriptive prompt string to get the user's approval.
            - **Special Case:** The approval prompt is automatically skipped for `chat_with_user` actions to provide a more fluid user experience.
        4.  If approved (or not in interactive mode), calls the ActionDispatcher.
        5.  Collects the ActionLog from the dispatcher.
        6.  Builds and returns the final ExecutionReport.

        Args:
            plan_content: A string containing the plan.
            interactive: A flag to enable/disable step-by-step user approval.

        Returns:
            An ExecutionReport summarizing the entire run.
        """
        pass
```

## 4. Domain Models (Input/Output)

-   **Input:** `plan_content: str`, `interactive: bool`
-   **Output:** `ExecutionReport` (from `execution_report.md`)
