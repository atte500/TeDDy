# Component: SessionService
- **Status:** Implemented

## 1. Purpose / Responsibility

The `SessionService` is responsible for managing the lifecycle of TeDDy sessions and turns on the local filesystem. It handles the creation of session directories, the management of `meta.yaml` and `turn.context` files, and the deterministic "Turn Transition Algorithm" that calculates the state for the next turn based on the current turn's outcome.

## 2. Ports

-   **Implements Outbound Port:** `ISessionManager`
-   **Uses Outbound Ports:**
    -   `IFileSystemManager`: For all directory and file operations.

## 3. Implementation Details / Logic

1.  **Session Bootstrapping (`create_session`):**
    -   Creates the session root and Turn 01 directory.
    -   Seeds `session.context` from `.teddy/init.context`, stripping comments.
    -   Fetches and saves the agent's system prompt to `01/[agent_name].xml`.
    -   Initializes `01/meta.yaml` with a `turn_id` and `creation_timestamp`.
2.  **Turn Transition (`transition_to_next_turn`):**
    -   Calculates the next turn ID (e.g., `01` -> `02`).
    -   Creates the next turn directory.
    -   Copies the current `[agent_name].xml` prompt file to the next turn.
    -   **Cost Persistence:** Updates `meta.yaml` with `parent_turn_id` links and cumulative cost. Every turn's `meta.yaml` MUST store `turn_cost` and `cumulative_cost` to ensure cost transparency and maintain a self-contained, auditable history for every turn without a centralized database.
    -   **Defensive Serialization:** Ensures all metadata is cast to primitive types before serialization to prevent hangs (see `ARCHITECTURE.md` rule on serialization).
    -   **Context Management:**
        -   Seeds the next `turn.context` with the current one. Reading is robust: if `turn.context` is missing or unreadable, it is treated as an empty set of paths.
        -   Parses `READ` and `PRUNE` actions from the `ExecutionReport` to update the next context.
        -   Always appends the current `report.md` to the next context to ensure the AI has history.

## 4. Data Contracts / Methods

### `create_session(name: str, agent_name: str) -> str`
-   **Description:** Bootstraps a new session directory and returns the root path.

### `get_latest_turn(session_name: str) -> str`
-   **Description:** Returns the directory path of the most recent turn in a session.

### `get_session_state(session_name: str) -> tuple[SessionState, str]`
-   **Description:** Determines the current state (EMPTY, PENDING_PLAN, COMPLETE_TURN) and latest turn path for a session.

### `transition_to_next_turn(plan_path: str, execution_report: ExecutionReport) -> str`
-   **Description:** Executes the Turn Transition Algorithm to prepare the next turn directory.

### `rename_session(old_name: str, new_name: str) -> str`
-   **Description:** Safely renames a session directory on the filesystem.
-   **Exceptions:** `ValueError` if the new name already exists.

### `get_latest_session_name() -> str`
-   **Description:** Identifies and returns the name of the most recently modified session.
-   **Exceptions:** `ValueError` if no sessions are found.

### `resolve_session_from_path(path: str) -> str`
-   **Description:** Resolves a session name from a given path (session root, turn dir, or file).
-   **Exceptions:** `ValueError` if the path is not inside a session.

## 5. Implementation Notes

-   **Dynamic Renaming:** The `rename_session` method is provided to safely move session directories. The `SessionOrchestrator` uses this to rename timestamped sessions to a slugified version of the first plan's title (H1) after generation.
-   **Robust Context Reading:** Uses `_read_context_file` to handle missing or malformed `turn.context` files gracefully, treating them as empty.
