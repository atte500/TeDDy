# Component Design: SessionService
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/session_service.py`](/src/teddy_executor/core/services/session_service.py)

## Purpose
Implements the `ISessionManager` outbound port. It manages the on-disk lifecycle of sessions and turns: claiming session roots, bootstrapping turns, persisting metadata, and computing the next turn's context through the turn transition algorithm.

## Consumers
- [`SessionOrchestrator`](./session_orchestrator.md): Drives the turn transition algorithm.
- [`SessionPlanner`](./session_planner.md): Reads session state during interactive planning.
- [CLI Adapter](../../adapters/inbound/cli.md): Starts, resumes, and renames sessions.
- [Composition Root](/src/teddy_executor/container.py): Registers `SessionService` and binds it to `ISessionManager`.

## Dependencies
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Performs directory and file operations.
- [`ISessionRepository`](/src/teddy_executor/core/ports/outbound/session_repository.py): Persists metadata and discovers turns.
- [`ITimeService`](/src/teddy_executor/core/ports/outbound/time_service.py): Supplies local and UTC timestamps.
- [`IPromptManager`](/src/teddy_executor/core/ports/outbound/prompt_manager.py): Resolves and composes agent prompts.
- [`IInitUseCase`](../ports/inbound/init.md): Ensures initialization before seeding context.
- [`IConfigService`](../ports/outbound/config_service.md): Reads the message-turn preservation toggle.

## Class Invariants
- `single_folder_lifetime`: A session keeps one folder for its lifetime; a turn may rename it once.
- `exclusive_root_claim`: Session roots are claimed atomically, so concurrent creators never merge ledgers.
- `primitive_serialization`: All metadata is cast to primitive types before serialization.
- `robust_context_read`: A missing or unreadable `turn.context` is treated as empty.

## Inbound Ports
None — the service implements an outbound port and is consumed through `ISessionManager`.

## Outbound Ports
- **`ISessionManager`**: The implemented contract; see Operations for the exposed behavior.

## Data Contracts
- **`SessionOptions`** (`teddy_executor.core.domain.models.session`): The session creation DTO.
- **`SessionState`** (str Enum): `EMPTY`, `PENDING_PLAN`, `COMPLETE_TURN`.
- **`ExecutionReport`** (`teddy_executor.core.domain.models`): Carried into `transition_to_next_turn`.

## Operations

### `create_session(options) -> str`
- **Preconditions:** `options` is a valid `SessionOptions`.
- **Postconditions:** Atomically claims a session root, bootstraps Turn 1, seeds `session.context`, writes the composed system prompt, and returns the claimed root path.

### `get_session_state(session_name) -> tuple[SessionState, str]`
- **Preconditions:** The session exists.
- **Postconditions:** Returns the state derived from the latest turn and the latest turn path.

### `transition_to_next_turn(plan_path, execution_report=None, turn_cost=0.0, is_validation_failure=False, pruned_paths=None) -> str`
- **Preconditions:** `plan_path` points to the current turn's plan.
- **Postconditions:** Creates the next turn directory within the same session, prunes and re-seeds context, persists cumulative cost, and returns the next directory path.

### `rename_session(old_name, new_name) -> str`
- **Preconditions:** `old_name` exists.
- **Postconditions:** Renames the session directory and returns the new path.
- **Exceptions:** `ValueError` when `new_name` already exists.

### `load_turn_meta(turn_dir) -> dict` and `save_turn_meta(turn_dir, data) -> None`
- **Preconditions:** None, and `turn_dir` exists respectively.
- **Postconditions:** Loads or persists the turn's `meta.yaml` through the repository seam.

### `set_session_agent(session_name, agent_name) -> None`
- **Preconditions:** The session exists.
- **Postconditions:** Updates the session's agent and recomposes the session-root prompt for the new agent, removing stale prompt files.
