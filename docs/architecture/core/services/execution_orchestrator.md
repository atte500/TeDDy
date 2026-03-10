# Application Service: ExecutionOrchestrator

The `ExecutionOrchestrator` is the stateless core service responsible for the atomic execution of a plan. While it implements the `IRunPlanUseCase`, in the context of the interactive session workflow, it is typically wrapped by the `SessionOrchestrator`, which handles the stateful side-effects like turn transitions.

## 1. Design Principles

-   **Stateless Execution:** This service is designed to be purely execution-focused, with no knowledge of session history or future turns.
-   **Use Case Controller:** This service directly implements the `run_plan` use case.
-   **Coordination, Not Creation:** Its role is to orchestrate calls to other single-responsibility services (`PlanParser`, `ActionDispatcher`). It does not contain complex business logic itself.
-   **State Management:** It manages the state of the execution run, collecting `ActionLog` objects and building the final `ExecutionReport`.
-   **Port-driven Interaction:** All side effects (user interaction, file I/O) are delegated through outbound ports, keeping the orchestrator's logic pure and testable.

## 2. Dependencies

-   **Inbound Ports & Services:**
    -   `IPlanReviewer`: (Optional) To allow interactive review and modification of the plan.
    -   `ActionDispatcher`: To execute each action in the plan.
    -   `IEditSimulator`: To generate preview content for `EDIT` actions.
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

        1.  **Plan Review:** If an `IPlanReviewer` is provided, it is invoked to allow the user to modify the plan (deselect actions or edit parameters) before execution begins.
        2.  Loops through each action in the plan.
        2.  Checks for previous failures. If any action has failed (triggering the `halt_execution` flag), subsequent actions are automatically skipped to prevent cascading failures, and `IUserInteractor.notify_skipped_action` is called to warn the user.
        3.  **Action Isolation Enforcement:** Verifies terminal actions (`PROMPT`, `INVOKE`, `RETURN`) are executed in isolation. If a terminal action is part of a multi-action plan, it is automatically skipped.
        4.  **Control Flow Interception:** Intercepts `PRUNE`, `INVOKE`, and `RETURN` actions.
            - `PRUNE`: Automatically skipped in manual mode (context is not persistent).
            - `INVOKE`/`RETURN`: Always interrupts the flow to request manual confirmation from the user via `IUserInteractor.confirm_manual_handoff`, even in non-interactive mode.
        4.  **Action Confirmation:** If not intercepted and in interactive mode, coordinates a `ChangeSet` and calls `IUserInteractor.confirm_action`.
            - **Special Case:** The approval prompt is automatically skipped for `PROMPT` actions.
        5.  **Dispatch:** If approved (or not in interactive mode), calls the ActionDispatcher.
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
