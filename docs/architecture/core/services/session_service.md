# Component: SessionService
- **Status:** Active

## 1. Purpose / Responsibility

The `SessionService` is responsible for managing the lifecycle of TeDDy sessions and turns on the local filesystem. It handles the creation of session directories, the management of `meta.yaml` and `turn.context` files, and the deterministic "Turn Transition Algorithm" that calculates the state for the next turn based on the current turn's outcome. It also manages execution side-effects, such as automatically adding created or modified files to the next turn's working context.

## 3. Ports

-   **Implements Outbound Port:** `ISessionManager`
-   **Uses Outbound Ports:**
    -   `IFileSystemManager`: For all directory and file operations.
    -   `ISessionRepository`: For persistence and turn discovery.
    -   `IPromptManager`: For resolving agent prompts.

## 4. Implementation Details / Logic

1.  **Session Bootstrapping (`create_session`):**
    -   **Exclusive Root Claim:** Atomically claims the session root via `_claim_session_root(f"{timestamp}-{clean_name}")` BEFORE creating any files. If the root is occupied (concurrent same-name creation within the same second), the helper retries with an incremented trailing `-N` suffix following the continuation-name convention, so colliding creators land on distinct roots instead of silently overwriting each other's audit ledgers.
    -   Derives `turn_dir = f"{session_root}/01"` and creates it via the tolerant `create_turn_directory` (safe — the root is exclusively owned by the claim winner).
    -   Seeds `session.context` from `.teddy/init.context`, stripping comments.
    -   **Context Merging and Deduplication:** If `additional_context` is provided, it is merged into the `session.context` content after the `init.context` content. The merged list of paths is then deduplicated **preserving insertion order** using a `seen` set before joining with newlines. This ensures `session.context` never contains duplicate paths at creation time.
        -   **Critical Ordering:** The `initial_request.md` path is added to the merge list **before** deduplication occurs, so it is also deduplicated. Previously, it was appended after joining, which made it impossible to deduplicate.
        -   **Type Safety:** The `to_root_relative()` helper may return non-string types (e.g., `POSIXPathMock` in test environments). The path is explicitly wrapped with `str()` before appending to `clean_lines` to ensure `"\n".join()` receives all strings.
    -   **Prompt Relocation:** Fetches and saves the agent's system prompt exclusively to the session root as `{session_root}/system_prompt.xml`.
    -   Initializes `01/meta.yaml` with `turn_id`, `creation_timestamp`, and any optional LLM overrides (`model`, `provider`, `api_key`).
2.  **Turn Transition (`transition_to_next_turn`):**
    -   Calculates the next turn ID (e.g., `01` -> `02`).
    -   **Context Pruning:** The context-pruning block is delegated to the private `_prune_context_paths(paths, pruned_paths, next_session_dir)` helper (behavior-preserving SRP extraction).
    -   **Migration Trigger:** If the next ID is `"100"`, invokes `migrate_to_continuation`.
    -   **Cost Persistence:** Updates `meta.yaml` with `parent_turn_id` links and cumulative cost. Every turn's `meta.yaml` MUST store `turn_cost` and `cumulative_cost`.

3.  **Migration Algorithm (`migrate_to_continuation`):**
    -   Resolves next session name (e.g., `{name}-2`).
    -   **Exclusive Continuation Claim:** During migration, the continuation root is exclusive-claimed via `_claim_session_root` BEFORE `_clone_session_artifacts` runs; an occupied continuation name (e.g., a live sibling `...-foo-2` session) is skipped and the next free root (`...-foo-3`) is claimed. The claimed directory name drives ALL downstream persistence (turn dir, meta, context, cloned artifacts). Non-migration turn transitions are unaffected.
    -   Clones `session.context` and `system_prompt.xml` from the current session root to the new one.
    -   Transitions the current turn's `turn.context` to Turn 01 of the new session.
    -   **Defensive Serialization:** Ensures all metadata is cast to primitive types before serialization to prevent hangs (see `ARCHITECTURE.md` rule on serialization).
    -   **Context Management:**
        -   Seeds the next `turn.context` with the current one. Reading is robust: if `turn.context` is missing or unreadable, it is treated as an empty set of paths.
        -   Parses `READ` and `PRUNE` actions from the `ExecutionReport` to update the next context.
        -   Always appends the current `report.md` to the next context to ensure the AI has history.

## 5. Data Contracts / Methods

### `create_session(options: SessionOptions) -> str`
-   **Description:** Exclusively claims a new session root (retrying with an incremented `-N` suffix if occupied), bootstraps the session directory, merges additional context if provided, and returns the claimed root path.

### `_claim_session_root(base_name: str) -> str` (private)
-   **Description:** Atomically claims `.teddy/sessions/{candidate}` via `IFileSystemManager.create_directory_exclusive` (single atomic OS operation — no check-then-act window), iterating candidates `base_name`, then following the continuation-name convention (`_calculate_continuation_name`): `base-2`, `base-3`, ... Returns the first successfully claimed root path. This is the single shared uniqueness mechanism for both `create_session` and the turn-100 migration, guaranteeing concurrent same-name sessions never merge their audit ledgers.

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

## 6. Implementation Notes

-   **Dynamic Renaming:** The `rename_session` method is provided to safely move session directories. The `SessionOrchestrator` uses this to rename timestamped sessions to a slugified version of the first plan's title (H1) after generation.
-   **Robust Context Reading:** Uses `_read_context_file` to handle missing or malformed `turn.context` files gracefully, treating them as empty.
-   **Session Name Collision Guard:** `_claim_session_root` provides atomic exclusive creation of session roots (`mkdir()` without `exist_ok` via `IFileSystemManager.create_directory_exclusive`), eliminating the TOCTOU race where two concurrent creators both observe a free path. The retry chain follows the continuation-name convention. Covered by unit tests (helper retry chain, `create_session` collision, migration collision) and a sibling-integrity integration gate asserting both call sites leave a pre-existing sibling session's ledger byte-identical.
-   **Complexity Management:** The context-pruning block of `transition_to_next_turn` is extracted into the private `_prune_context_paths(paths, pruned_paths, next_session_dir)` helper, keeping the transition method under the project's cyclomatic-complexity threshold.
