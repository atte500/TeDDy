# Component: SessionOrchestrator
- **Status:** Implemented
- **Introduced in:** [Slice 09-04](/docs/project/slices/09-04-core-session-context-engine.md)

## 1. Purpose / Responsibility

The `SessionOrchestrator` is a decorator-style service that wraps the stateless `ExecutionOrchestrator` to provide stateful session behavior. It implements the `IRunPlanUseCase` but adds side-effects required for the interactive session workflow, such as persisting the execution report and triggering turn transitions.

## 2. Ports

-   **Implements Inbound Port:** `IRunPlanUseCase`
-   **Uses Outbound Ports:**
    -   `ExecutionOrchestrator`: (Internal dependency) For core execution logic.
    -   `ISessionManager` (SessionService): For triggering turn transitions.
    -   `IFileSystemManager`: For persisting the formatted report.
    -   `IMarkdownReportFormatter`: For formatting the `ExecutionReport` before saving.

## 3. Implementation Details / Logic

1.  **Stateless Execution:** Delegated to the wrapped `ExecutionOrchestrator`.
2.  **Session Mode Detection:** If a `plan_path` is provided, the orchestrator enters "Session Mode".
3.  **Validation Phase (Session Mode):**
    -   Resolves context paths from `session.context` and `turn.context`.
    -   Calls `PlanValidator.validate(plan, context_paths)`.
    -   If errors exist, triggers the **Automated Re-plan Loop**.
4.  **Automated Re-plan Loop:**
    -   Generates a `report.md` in the current turn containing the validation errors.
    -   Calls `SessionService.transition_to_next_turn` with `is_validation_failure=True`. This ensures the failure report is NOT added to the next turn's context.
    -   Calls `PlanningService.generate_plan` for the new turn, using a structured feedback payload (Errors + Original Plan) as the user message.
5.  **Report Persistence:** In Session Mode, the `ExecutionReport` is formatted and saved to `report.md` in the turn directory.
6.  **Stateful Transition:** After saving the report, it calls `SessionService.transition_to_next_turn` to prepare the next stage of the session.

## 4. Data Contracts / Methods

### `execute(...) -> ExecutionReport`
-   **Description:** Implements the `IRunPlanUseCase`. If `plan_path` is present, it layers stateful session side-effects over the core execution.

### `resume(session_name: str, interactive: bool = True)`
-   **Description:** Implements the session state machine. Detects the state of the latest turn (EMPTY, PENDING_PLAN, COMPLETE_TURN) and triggers the appropriate action (Planning, Execution, or Transitioning).
