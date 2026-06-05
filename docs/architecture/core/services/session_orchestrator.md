# Component: SessionOrchestrator
- **Status:** Implemented

## 1. Purpose / Responsibility

The `SessionOrchestrator` is a decorator-style service that wraps the stateless `ExecutionOrchestrator` to provide stateful session behavior. It is responsible for passing the session's cache directory to `ContextService.get_context()` to enable web content caching. It implements the `IRunPlanUseCase` but adds side-effects required for the interactive session workflow, such as persisting the execution report and triggering turn transitions.

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
### 3. Cache Directory Derivation: Before calling `ContextService`, the orchestrator derives the session's web content cache directory from `plan_path`:
    - `plan_path` = full path to the turn's `plan.md` (e.g., `.../mysession/01/plan.md`)
    - `cache_dir` = `str(Path(plan_path).parent.parent)` -> `.../mysession` (session root)
    - The cache file lives at `<session_root>/.web_cache.json`
    - `cache_dir` is passed as the final keyword argument to `ContextService.get_context(cache_dir=cache_dir)`
    - The `Path` import (`from pathlib import Path`) is already present in `session_orchestrator.py`; no additional imports required.
4.  **Validation Phase (Session Mode):**
    -   Resolves context paths from `session.context` and `turn.context`.
    -   **Context Harvesting**: Before validation, identifies unselected (pruned) context items and records them in `plan.metadata["pruned_context"]`. This ensures persistence even if the turn fails validation.
    -   Calls `PlanValidator.validate(plan, context_paths)`.
    -   If errors exist, triggers the **Automated Re-plan Loop**.
5.  **Context Assembly (with Cache):** When calling `ContextService.get_context()`, the `cache_dir` (session root path) is passed as `cache_dir` parameter to enable web content caching. URLs in session/turn context files are checked against the cache before network fetches.
6.  **Automated Re-plan Loop:**
    -   Generates a `report.md` in the current turn containing the validation errors.
    -   Triggers the replan via `SessionLifecycleManager.trigger_replan`, propagating the current `Plan` object.
    -   Calls `SessionService.transition_to_next_turn` with `is_validation_failure=True`, and extracts `pruned_context` from the plan metadata to ensure pruned files remain excluded from the next turn's manifest.
    -   Calls `PlanningService.generate_plan` for the new turn, using a structured feedback payload (Errors + Original Plan) as the user message. Relies on `PlanningService` defensive resolution to carry forward session history.
7.  **Planning Visibility:** Centralizes planning triggers to provide consistent UI feedback, extracting the Turn ID from the directory name and the agent name from metadata to display a progress message (e.g., `[01] Planning Turn with pathfinder...`) before LLM calls. The message is wrapped in `[cyan]` Rich style tags for consistent terminal coloring.
8.  **Telemetry Display:** After plan generation, retrieves metadata and displays model name, context token usage, and cumulative session cost to the user. The formatted telemetry strings are wrapped in `[dim]` Rich style tags to visually separate them as secondary information.
9.  **Auto-Naming:** Sessions created without a name (Turn 01) use a temporary timestamped name. The orchestrator automatically renames the session directory based on the slugified H1 title of the first generated plan. This allows the AI to suggest a meaningful name based on the actual content of the initial request.
10. **Report Persistence:** In Session Mode, the `ExecutionReport` is formatted and saved to `report.md` in the turn directory.
11. **Stateful Transition:** After saving the report, it calls `SessionService.transition_to_next_turn` to prepare the next stage of the session.

## 4. Data Contracts / Methods

### `execute(...) -> ExecutionReport`
-   **Description:** Implements the `IRunPlanUseCase`. If `plan_path` is present, it layers stateful session side-effects over the core execution.
-   **Cache Integration:** When in session mode (`plan_path` present), derives `cache_dir = str(Path(plan_path).parent.parent)` and passes it to `ContextService.get_context(cache_dir=cache_dir)` to enable web content caching.

### `resume(session_name: str, interactive: bool = True)`
-   **Description:** Implements the session state machine. Detects the state of the latest turn (EMPTY, PENDING_PLAN, COMPLETE_TURN) and triggers the appropriate action.
-   **Algorithm:**
    1.  Get current session state (EMPTY, PENDING_PLAN, COMPLETE_TURN).
    2.  **EMPTY**: Prompt for instructions -> Generate Plan -> Resolve actual path via `SessionService` -> Call `execute`.
    3.  **PENDING_PLAN**: Call `execute(plan_path=...)`.
    4.  **COMPLETE_TURN**: Transition to next turn -> Prompt for instructions -> Generate Plan -> Resolve actual path via `SessionService` -> Call `execute`.
-   **Recursion Safety:** To prevent recursion loops and handle dynamic renaming, the state machine resolves the current turn's path from the `SessionService` after planning/renaming and delegates directly to `execute`.
