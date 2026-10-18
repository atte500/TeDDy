# Component Design: LocalFileSystemAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/local_file_system_adapter.py`](/src/teddy_executor/adapters/outbound/local_file_system_adapter.py)

## Purpose
Implements the `IFileSystemManager` outbound port for the local disk. It resolves every path against a controlled project root, applies exclusive-create and newline-deterministic write semantics, and delegates fuzzy edits to the `IEditSimulator`.

## Consumers
- [`ActionFactory`](../../core/services/action_factory.md): Binds the create, edit, and local read methods to their actions.
- [`ExecutionOrchestrator`](../../core/services/execution_orchestrator.md): Reads plan files and writes temporary plans.
- [`PlanValidator`](../../core/services/plan_validator.md): Inspects paths during pre-flight validation.
- [Composition Root](/src/teddy_executor/container.py): Constructs the adapter with the edit simulator, the root directory, and the read cap.

## Dependencies
- [`IEditSimulator`](../../core/ports/inbound/edit_simulator.md): Applies FIND/REPLACE edits during `edit_file`.
- **`filesystem_helpers`** (`teddy_executor.adapters.outbound.filesystem_helpers`): Loads the ignore spec and walks the tree recursively.
- **`truncate_lines`** (`teddy_executor.core.utils.string`): Applies the head cap on `read_file`.

## Class Invariants
- `root_containment`: Every relative path resolves against the project root; leading slashes and Windows drive letters are stripped before joining.
- `exclusive_create`: `create_file` uses exclusive mode (`x`) unless `overwrite` is set, and re-raises a domain `FileAlreadyExistsError` on collision.
- `newline_deterministic_writes`: `write_file`, `create_file`, `edit_file`, and `open_file_for_append` use `newline=""`, so content is emitted verbatim on every OS.
- `head_truncation`: `read_file` truncates at the head to `max_read_lines` (default `1000`); `read_raw_file` and `read_files_in_vault` bypass the cap.
- `lazy_ignore_spec`: The ignore specification and the resolved root are computed once and cached on the instance.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IFileSystemManager`**: The driven contract implemented by this adapter. See the [IFileSystemManager design](../../core/ports/outbound/file_system_manager.md).

## Data Contracts
- **`EditPair`** (`TypedDict`): `find: str`, `replace: str`, `match_all: bool`.
- **`edit_file` return:** `list[float]` — the per-edit similarity scores.
- **`read_files_in_vault` return:** `dict[str, str | None]`, where `None` marks a missing file.
- **Configuration key:** `max_read_lines` sets the default read cap (`1000`).

## Operations

### `create_file(path, content, overwrite=False) -> None`
- **Preconditions:** `path` resolves inside the project root.
- **Postconditions:** Creates the file and its parent directories, writing the content verbatim with LF preserved.
- **Exceptions:** `FileAlreadyExistsError` when the file exists and `overwrite` is unset; `OSError` on any other I/O failure.

### `read_file(path) -> str` and `read_raw_file(path) -> str`
- **Preconditions:** `path` resolves inside the project root.
- **Postconditions:** `read_file` returns head-truncated content; `read_raw_file` returns the full content.
- **Exceptions:** `FileNotFoundError` when no file exists at `path`.

### `write_file(path, content) -> None`
- **Postconditions:** Upserts the file with LF-verbatim content.

### `edit_file(path, edits, similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD, match_all=False) -> list[float]`
- **Preconditions:** The file exists and each edit carries a `find` block.
- **Postconditions:** Rewrites the file through the injected `IEditSimulator`, writes the simulated content verbatim, and returns the similarity scores.
- **Exceptions:** Propagates the simulator's `SearchTextNotFoundError` and `MultipleMatchesFoundError`.

### `read_files_in_vault(paths) -> dict[str, str | None]`
- **Postconditions:** Returns the full content per path, or `None` for a missing file.

### `create_directory_exclusive(path) -> bool`
- **Postconditions:** Creates the directory atomically and returns `True`; returns `False` when the directory already exists. Any other error propagates.

### Other operations
`path_exists`, `is_dir`, `list_directory`, `list_directory_recursive`, `create_directory`, `get_mtime`, `move_directory`, `remove_file`, `get_context_paths`, and `resolve_paths_from_files` complete the port surface.
