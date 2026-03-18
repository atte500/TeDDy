**Status:** Implemented

## 1. Purpose / Responsibility

The `ISessionManager` port defines the interface for managing the stateful lifecycle of TeDDy sessions, including turn transitions, metadata persistence, and context resolution.

## 2. Ports

- **Type:** Outbound Port
- **Used by:** `SessionOrchestrator`
- **Implemented by:** `SessionService`

## 3. Implementation Details / Logic

This port abstracts the logic for creating turn directories, managing the `turn.context` file, and persisting metadata in `meta.yaml`.

## 4. Data Contracts / Methods

### `create_session(name: str, agent_name: str) -> str`
- **Description:** Initializes a new session directory and bootstraps it for Turn 1.
- **Returns:** The path to the new session directory.

### `get_latest_turn(session_name: str) -> str`
- **Description:** Identifies the latest turn directory in the specified session.

### `get_session_state(session_name: str) -> tuple[SessionState, str]`
- **Description:** Determines if the latest turn is EMPTY, PENDING_PLAN, or COMPLETE_TURN.

### `transition_to_next_turn`
- **Description:** Creates the next turn directory and propagates context and cost metadata.
- **Arguments:**
    - `plan_path` (str)
    - `execution_report` (Optional[ExecutionReport])
    - `is_validation_failure` (bool)
    - `turn_cost` (Optional[float]): The USD cost of the current turn to be recorded in meta.yaml.
- **Returns:** The path to the next turn directory.

### `rename_session`
- **Description:** Safely renames a session directory on the filesystem.
- **Arguments:**
    - `old_name` (str)
    - `new_name` (str)
- **Returns:** The new path to the session directory.
- **Exceptions:** `ValueError` if the new name already exists.

### `get_latest_session_name`
- **Description:** Identifies and returns the name of the most recently modified session.
- **Returns:** The session name as a string.
- **Exceptions:** `ValueError` if no sessions are found.

### `resolve_session_from_path`
- **Description:** Resolves a session name from a given path (session root, turn dir, or file).
- **Arguments:**
    - `path` (str)
- **Returns:** The session name as a string.
- **Exceptions:** `ValueError` if the path is not inside a session.

### `resolve_context_paths(plan_path: str) -> dict[str, list[str]]`
- **Description:** Locates context files relative to the plan path and returns their contents.
