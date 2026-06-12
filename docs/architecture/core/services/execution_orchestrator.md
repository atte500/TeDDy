# Application Service: ExecutionOrchestrator

The `ExecutionOrchestrator` is the stateless core service responsible for the atomic execution of a plan. While it implements the `IRunPlanUseCase`, in the context of the interactive session workflow, it is typically wrapped by the `SessionOrchestrator`, which handles the stateful side-effects like turn transitions.

## 1. Design Principles

-   **Stateless Execution:** This service is designed to be purely execution-focused, with no knowledge of session history or future turns.
-   **Use Case Controller:** This service directly implements the `run_plan` use case.
-   **Coordination, Not Creation:** Its role is to orchestrate calls to other single-responsibility services (`PlanParser`, `ActionDispatcher`). It does not contain complex business logic itself.
-   **State Management:** It manages the state of the execution run, collecting `ActionLog` objects and building the final `ExecutionReport`.
-   **Port-driven Interaction:** All side effects (user interaction, file I/O) are delegated through outbound ports, keeping the orchestrator's logic pure and testable.

## Primary Responsibilities

### Console Visibility
After the interactive plan review (via `_perform_interactive_review`) and before any action execution logs are printed, the orchestrator prints a single line containing the plan status emoji and plan title to stderr. This provides the user with immediate semantic context in the terminal scrollback.

**Injection Point:** Inside `execute()`, after `reviewed_plan = self._perform_interactive_review(...)` returns, before `action_logs = self._process_plan_actions(...)` is called.

**Format:** `typer.secho(f"{emoji} {plan.title}", fg=typer.colors.CYAN, err=True)`

**Emoji Extraction:** The status emoji (🟢, 🟡, 🔴) is extracted from `plan.metadata.get("Status", "")` using the regex pattern `[🟢🟡🔴]`. If no emoji is found, a fallback "❓" is used. This logic is encapsulated in a private helper `_extract_status_emoji()` within the module.

### Message Visibility
After all actions have been processed (via `_process_plan_actions`) and before the `ExecutionReport` is assembled, the orchestrator prints a user message line if one was provided. The message is resolved from the `message` parameter first, falling back to `plan.metadata.get("user_request")` (which is populated when the user presses 'm' in the TUI to provide an additional message).

**Injection Point:** Inside `execute()`, after `action_logs = self._process_plan_actions(...)` returns, before `return self._report_assembler.assemble(...)` is called.

**Format:** `typer.secho(f"User Message: {resolved_message}", fg=typer.colors.YELLOW, err=True)`

If no message is provided (both `message` and `plan.metadata.user_request` are empty/None), no "User Message:" line is printed.

## 2. Dependencies

-   **Inbound Ports & Services:**
    -   `IPlanReviewer`: (Optional) To allow interactive review and modification of the plan.
    -   `ActionDispatcher`: To execute each action in the plan.
    -   `IEditSimulator`: To generate preview content for `EDIT` actions.
-   **Outbound Ports:**
    -   `IUserInteractor`: To display messages and prompt for step-by-step approval.
    -   `IFileSystemManager`: For contextual file reading.
    -   `IExecutionReportAssembler`: To construct the final report.

## 3. Core Logic: Message Protocol
The orchestrator distinguishes between "Acting Turns" and "Communication Turns":
- **Acting Turns:** Plans containing standard actions. These require user approval via `IPlanReviewer` (TUI) and `IUserInteractor` (step-by-step).
- **Communication Turns:** Plans containing a single `MESSAGE` action. These bypass the `IPlanReviewer` and display content directly via `IUserInteractor.display_message`.
- **Validation:** Communication turns MUST NOT be empty. An empty message triggers a `PlanValidationError`.
- **Deprecation:** Legacy actions (`PROMPT`, `INVOKE`, `RETURN`) trigger terminal-only warnings via `IUserInteractor` to alert the developer. These warnings are EXCLUDED from the `ExecutionReport` to prevent AI confusion and hallucinations.

## 4. Public Interface

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
        3.  **Control Flow Interception:** Intercepts `PRUNE`, `INVOKE`, and `RETURN` actions.
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
