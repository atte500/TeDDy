# Vertical Slice: Refactor Context Management

-   **Stage:** `executor`
-   **Status:** `Implemented`

## 1. Goal

Improve the clarity and explicitness of the context management system by:
1.  Changing the default context file extension from `.txt` to `.context` for better semantic identification.
2.  Making the inclusion of `.gitignore` rules an explicit, opt-in choice rather than a default behavior, giving users finer control over the context provided to the AI.

## 2. Scope of Work

-   [ ] **Acceptance Test:** Create a new, disabled acceptance test `test_context_refactor.py` that asserts:
    -   The `context` command correctly sources configuration from `.teddy/*.context` files.
    -   The `context` command *does not* filter files based on `.gitignore` rules by default.
-   [ ] **Domain/Service Layer:**
    -   [ ] Modify `LocalRepoTreeGenerator` to remove the automatic loading of `.gitignore`. It should only process ignore files provided to it.
    -   [ ] Modify `ContextService` (or relevant service) to search for `.context` files instead of `.txt` files in the `.teddy/` directory.
-   [ ] **Documentation:**
    -   [ ] Update `ARCHITECTURE.md` to reflect the new `.context` file convention and the change in `.gitignore` handling.
    -   [ ] Update `README.md` to accurately describe the `context` command's new behavior.
-   [ ] **Activation:**
    -   [ ] Enable the new acceptance test.
    -   [ ] Wire up the new logic in the application's composition root (`main.py`).
    -   [ ] Ensure all tests pass.

## 3. Architectural Changes

### `LocalRepoTreeGenerator` (Adapter)

-   **Change:** The adapter will be modified to no longer automatically discover and parse the root `.gitignore` file.
-   **Rationale:** This change makes the context generation more explicit. The generator should be a "dumb" tool that only processes what it's given. The responsibility for deciding *which* ignore files to use (including `.gitignore`) belongs higher up, in the application service layer that orchestrates the context generation.

### `ContextService` (Application Service)

-   **Change:** The service will be updated to look for files with a `.context` extension inside the `.teddy/` configuration directory instead of `.txt`.
-   **Rationale:** As argued in the user's request, using a dedicated `.context` extension provides better semantic clarity and avoids potential conflicts with generic `.txt` files. It makes the purpose of these files unambiguous within the TeDDy ecosystem.

### Documentation (`ARCHITECTURE.md`, `README.md`)

-   **Change:** Both documents will be updated to reflect the new file extensions and the fact that `.gitignore` is no longer processed by default. The documentation will clarify that if a user wants `.gitignore` rules to be applied, they must explicitly include the `.gitignore` file in their context configuration.
-   **Rationale:** Documentation must remain the single source of truth for the system's behavior.
