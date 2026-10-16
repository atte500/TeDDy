# Component Design: SessionPlanner
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/session_planner.py`](/src/teddy_executor/core/services/session_planner.py)

## Purpose
Handles interactive turn planning. It triggers the `PlanningService` to generate a plan for the current turn, delegates context-manifest resolution to that service, and returns the session directory name so the orchestrator can rename an unnamed session.

## Consumers
- [SessionLifecycleManager](/src/teddy_executor/core/services/session_lifecycle_manager.py): Calls `trigger_new_plan` to start a turn's planning phase.
- [SessionPorts](/src/teddy_executor/core/domain/models/planning_ports.py): Declares the planner in the session ports bundle.
- [Composition Root](/src/teddy_executor/container.py): Constructs the planner and injects its collaborators.

## Dependencies
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Injected for filesystem access.
- [`PlanningService`](./planning_service.md): Generates the plan and resolves context manifests.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Injected for user interaction.
- [`ISessionManager`](../ports/outbound/session_manager.md): Injected for session-level metadata.

## Class Invariants
- `delegated_resolution`: The planner passes `context_files=None` to `PlanningService.generate_plan` and never builds a context manifest itself.
- `single_planning_call`: `trigger_new_plan` issues exactly one `generate_plan` call per invocation.
- `cancel_sentinel`: A `None` plan path yields the `("CANCELLED", None)` result.

## Inbound Ports
None — the planner is a concrete service consumed through the session ports bundle.

## Outbound Ports
- **`PlanningService`**: The planning use case consumed by `trigger_new_plan`.
- **`IFileSystemManager`**, **`IUserInteractor`**, **`ISessionManager`**: Injected collaborators; see Dependencies.

## Data Contracts
- **`ProjectContext`** (`teddy_executor.core.domain.models`): The gathered context threaded back to the caller.
- **Return tuple:** `(session_name, gathered_context)`; `session_name` is the session directory name, or `"CANCELLED"`.

## Operations

### `trigger_new_plan(turn_dir, message=None) -> tuple[str, Optional[ProjectContext]]`
- **Preconditions:** `turn_dir` is the current turn directory.
- **Postconditions:** Returns `(session_name, gathered_context)`. The `ProjectContext` gathered by `PlanningService.generate_plan` is threaded to the caller instead of being discarded, enforcing the single-gather-per-turn contract.
- **Exceptions:** None raised by the planner itself.
