# Component Design: ISessionManager
- **Status:** Implemented
- **Classification:** Core Outbound Port
- **Source:** [`src/teddy_executor/core/ports/outbound/session_manager.py`](/src/teddy_executor/core/ports/outbound/session_manager.py)

## Purpose
Defines the outbound port for the stateful lifecycle of a session: creating sessions, reasoning about turn state, persisting metadata, resolving names, and transitioning between turns. It lets `SessionOrchestrator` manage the turn ledger without touching the file system directly.

## Consumers
- [`SessionOrchestrator`](../../services/session_orchestrator.md): Drives the turn transition algorithm.
- [`SessionPlanner`](../../services/session_planner.md): Reads session state during interactive planning.
- [CLI Adapter](../../../adapters/inbound/cli.md): Starts, resumes, and renames sessions.

## Dependencies
- **`SessionOptions`** (`teddy_executor.core.domain.models.session`): The creation DTO passed to `create_session`.
- **`ExecutionReport`** (`teddy_executor.core.domain.models`): Carried into `transition_to_next_turn`.

## Class Invariants
- `runtime_checkable`: The protocol supports `isinstance` checks.
- `single_folder_lifetime`: A session keeps one folder for its lifetime; a turn may rename it once.
- `usage_counter_contract`: Turn metadata always carries the four usage counters as integers; the first turn seeds them to `0` and each transition accumulates, so a whole-meta reader renders the cache ratio without a missing-key branch.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`ISessionManager`**: The driven contract consumed by core services and implemented by `SessionService`.

## Data Contracts
- **`SessionState`** (str Enum): `EMPTY`, `PENDING_PLAN`, `COMPLETE_TURN`.
- **`EXECUTION_STARTED_MARKER`** (str constant, `"execution.started"`): The turn-scoped filename written into a session turn directory when execution begins; the resume gate reads it to tell a mid-execution kill from a never-dispatched turn. It lives only while the turn is in flight: `SessionLifecycleManager.finalize_turn` removes it once `report.md` is written, and a leftover marker beside a report is inert because `get_session_state` resolves `COMPLETE_TURN` from the report first.
- **`TURN_USAGE_META_KEYS`** (tuple constant): The four turn-metadata keys carrying provider cache accounting — `prompt_tokens`, `cached_tokens`, `cumulative_prompt_tokens`, `cumulative_cached_tokens`. Every value is an `int`, and absent provider data persists as `0`.

## Operations

### `create_session(options) -> str`
- **Preconditions:** `options` is a valid `SessionOptions`.
- **Postconditions:** Creates the session directory, bootstraps Turn 1, and returns its path.

### `get_latest_turn(session_name) -> str`
- **Preconditions:** The session exists.
- **Postconditions:** Returns the latest turn directory path.

### `get_session_state(session_name) -> tuple[SessionState, str]`
- **Preconditions:** The session exists.
- **Postconditions:** Returns the state derived from the latest turn and its path.

### `get_cumulative_cost(session_name) -> float`
- **Preconditions:** The session exists.
- **Postconditions:** Returns the cumulative cost recorded in the latest turn metadata.

### `load_turn_meta(turn_dir) -> dict[str, Any]`
- **Preconditions:** None.
- **Postconditions:** Returns the parsed `meta.yaml`, or an empty dict when absent.

### `save_turn_meta(turn_dir, meta) -> None`
- **Preconditions:** `turn_dir` exists.
- **Postconditions:** Persists `meta` to the turn's `meta.yaml`.

### `transition_to_next_turn(plan_path, execution_report=None, turn_cost=0.0, is_validation_failure=False, pruned_paths=None) -> str`
- **Preconditions:** `plan_path` points to the current turn's plan.
- **Postconditions:** Creates the next turn directory, propagates context, cost, and cumulative usage metadata, and returns its path.

### `resolve_context_paths(plan_path) -> dict[str, list[str]]`
- **Preconditions:** `plan_path` exists.
- **Postconditions:** Returns context paths and their contents resolved relative to the plan.

### `rename_session(old_name, new_name) -> str`
- **Preconditions:** `old_name` exists.
- **Postconditions:** Renames the session directory and returns the new path.
- **Exceptions:**
  - `ValueError`: Target `new_name` already exists.

### `get_latest_session_name() -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the most recently modified session name.
- **Exceptions:**
  - `ValueError`: No sessions exist in the workspace.

### `resolve_session_from_path(path) -> str`
- **Preconditions:** `path` is within a session.
- **Postconditions:** Returns the session name for the given session root, turn directory, or file.
- **Exceptions:**
  - `ValueError`: Specified `path` does not reside inside a session directory.

### `resolve_session_from_slug(slug) -> str`
- **Preconditions:** At least one session exists.
- **Postconditions:** Returns the session matching the timestamp-stripped slug (exact, case-insensitive; latest wins).
- **Exceptions:**
  - `ValueError`: No existing session matches the provided slug.

### `to_root_relative(turn_dir, filename) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the root-relative path for a file in a turn directory.

### `preserve_turn_in_session_context(turn_dir) -> None`
- **Preconditions:** `turn_dir` exists.
- **Postconditions:** Admits the turn's plan and report to `session.context` when the turn qualifies for preservation.

### `set_session_agent(session_name, agent_name) -> None`
- **Preconditions:** The session exists.
- **Postconditions:** Updates the session's agent in metadata and replaces its prompt file with the new agent's prompt.
