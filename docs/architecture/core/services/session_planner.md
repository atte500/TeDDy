# Component: SessionPlanner
- **Status:** Implemented

## 1. Purpose / Responsibility

The `SessionPlanner` handles the interactive turn planning process. It orchestrates the flow of prompting the user for instructions and triggering the `PlanningService` to generate a plan. It also handles the logic for providing session names upon successful planning.

## 2. Ports

-   **Uses Outbound Ports:**
    -   `IFileSystemManager`: To check for existing reports/metadata.
    -   `IPlanningUseCase` (PlanningService): To generate the actual plan.
    -   `IUserInteractor`: To display messages and gather input.
    -   `ISessionManager` (SessionService): For session-level metadata.

## 3. Implementation Details / Logic

1.  **Instruction Gathering:** Determines the user's intent by checking CLI arguments, then falling back to previous execution reports or prompting the user.
2.  **Delegated Resolution:** It no longer manually constructs context manifests. Instead, it calls `PlanningService.generate_plan` with `context_files=None`, relying on the service's defensive resolution logic to find `session.context` and `turn.context`.
3.  **Session Naming:** Returns the name of the session directory upon successful generation, facilitating dynamic renaming in the orchestrator.

## 4. Data Contracts / Methods

### `trigger_new_plan(turn_dir: str, message: Optional[str] = None) -> tuple[str, Optional[ProjectContext]]`
-   **Description:** Orchestrates the planning turn.
-   **Returns:** `(session_name, gathered_context)` — the session name if successful, or `("CANCELLED", None)`. The `ProjectContext` gathered by `PlanningService.generate_plan` is threaded to the caller (the `SessionLifecycleManager` funnel, which passes it to `SessionOrchestrator.execute`) instead of being discarded, enforcing the single-gather-per-turn contract.
