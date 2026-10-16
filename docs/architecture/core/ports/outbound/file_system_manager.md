# Component Design: IFileSystemManager
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/file_system_manager.py`](/src/teddy_executor/core/ports/outbound/file_system_manager.py)

## Purpose
Defines the outbound port for every file system operation the core needs: create, read, edit, move, list, and inspect paths. It isolates the core from `pathlib` and the operating system, so file behavior can be faked in tests.

## Consumers
- [`ContextService`](../../services/context_service.md): Reads context files and lists the repository tree.
- [`InitService`](../../services/init_service.md): Writes config, prompt, and template files.
- [`PlanValidator`](../../services/plan_validator.md): Checks path existence during pre-flight validation.
- [`PromptManager`](../../services/prompt_manager.md): Reads and writes session prompt files.
- [`SessionService`](../../services/session_service.md): Creates turn directories and persists metadata.
- [`SessionOrchestrator`](../../services/session_orchestrator.md): Manages turn directories during transitions.
- [`SessionPruningService`](../../services/session_pruning_service.md): Rewrites context manifests.
- [`ActionPorts`](../../domain/action_ports.md): Carries the port into the action layer.
- [TextualPlanReviewer](../../../adapters/inbound/textual_plan_reviewer.md): Opens files during review.
- [CLI Adapter](../../../adapters/inbound/cli.md): Resolves context paths for commands.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `protocol_contract`: The port is a `Protocol`; implementing adapters satisfy the structural contract.
- `utf8_encoding`: All text reads and writes use UTF-8.
- `atomic_create_directory`: `create_directory_exclusive` performs one atomic OS operation, so exactly one concurrent caller wins.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IFileSystemManager`**: The driven contract consumed by core services and implemented by the `LocalFileSystemAdapter`.

## Data Contracts
- **`edits` parameter** (`edit_file`): a list of `{"find": str, "replace": str}` blocks.
- **`edit_file` return:** a list of per-edit similarity scores.
- **`read_files_in_vault` return:** a mapping of path to content, with `None` for missing files.

## Operations

### `path_exists(path) -> bool`
- **Preconditions:** None.
- **Postconditions:** Returns `True` when a file or directory exists at `path`.

### `is_dir(path) -> bool`
- **Preconditions:** None.
- **Postconditions:** Returns `True` when `path` exists and is a directory.

### `list_directory(path) -> list[str]`
- **Preconditions:** `path` exists and is a directory.
- **Postconditions:** Returns the names of files and directories directly under `path`.

### `list_directory_recursive(path) -> list[str]`
- **Preconditions:** `path` exists and is a directory.
- **Postconditions:** Returns root-relative file paths, respecting ignore rules.

### `create_directory(path) -> None`
- **Preconditions:** None.
- **Postconditions:** Creates `path` and any missing parents; idempotent.

### `create_directory_exclusive(path) -> bool`
- **Preconditions:** None.
- **Postconditions:** Atomically creates `path`; returns `True` when this call created it and `False` when it already existed.
- **Exceptions:** Re-raises any error other than `FileExistsError` (Failure Transparency).

### `write_file(path, content) -> None`
- **Preconditions:** None.
- **Postconditions:** Writes `content` to `path`, creating or overwriting the file.

### `create_file(path, content, overwrite=False) -> None`
- **Preconditions:** None.
- **Postconditions:** Creates `path` with `content`; overwrites when `overwrite` is `True`.
- **Exceptions:** `FileExistsError` when the file exists and `overwrite` is `False`.

### `read_file(path) -> str`
- **Preconditions:** `path` exists.
- **Postconditions:** Returns the file content, subject to the `read.max_lines` cap.
- **Exceptions:** `FileNotFoundError` when no file exists at `path`.

### `read_raw_file(path) -> str`
- **Preconditions:** `path` exists.
- **Postconditions:** Returns the full, uncapped file content.
- **Exceptions:** `FileNotFoundError` when no file exists at `path`.

### `remove_file(path) -> None`
- **Preconditions:** `path` exists.
- **Postconditions:** Deletes the file.
- **Exceptions:** `FileNotFoundError` when no file exists at `path`.

### `edit_file(path, edits, similarity_threshold=0.95, match_all=False) -> list[float]`
- **Preconditions:** `path` exists; `similarity_threshold` is between 0.0 and 1.0.
- **Postconditions:** Applies each FIND/REPLACE block and returns the per-edit similarity scores.
- **Exceptions:** `FileNotFoundError` when `path` is missing; `SearchTextNotFoundError` when no match meets the threshold; `MultipleMatchesFoundError` on an ambiguous tie.

### `get_context_paths() -> list[str]`
- **Preconditions:** None.
- **Postconditions:** Returns a deduplicated list of paths found in `.teddy/*.context` files.

### `resolve_paths_from_files(file_paths) -> list[str]`
- **Preconditions:** Each entry in `file_paths` exists.
- **Postconditions:** Returns a sorted, unique list of non-commented paths found in the given context files.

### `read_files_in_vault(paths) -> dict[str, str | None]`
- **Preconditions:** None.
- **Postconditions:** Returns full, uncapped content for found files and `None` for missing files.

### `get_mtime(path) -> float`
- **Preconditions:** `path` exists.
- **Postconditions:** Returns the modification timestamp.

### `move_directory(old_path, new_path) -> None`
- **Preconditions:** `old_path` exists.
- **Postconditions:** Moves or renames the directory to `new_path`.

### `open_file_for_append(path) -> TextIO`
- **Preconditions:** None.
- **Postconditions:** Returns a writable handle opened in append mode, creating parent directories as needed.
- **Exceptions:** `IOError` when the file cannot be opened.
