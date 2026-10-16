# Component Design: SystemEnvironmentAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/system_environment_adapter.py`](/src/teddy_executor/adapters/outbound/system_environment_adapter.py)

## Purpose
Implements the `ISystemEnvironment` outbound port with the Python standard library. It locates commands, reads environment variables, runs external processes, and manages temporary files for the console adapters.

## Consumers
- [`ConsoleTooling`](./console_tooling.md): Discovers editors and diff viewers on `PATH` through `which`.
- [`ConsoleInteractor`](./console_interactor.md): Launches the editor and diff tools through `run_command` and stages preview files through `create_temp_file`.

## Dependencies
- **`restore_cooked_mode`** (`teddy_executor.core.utils.terminal`): Restores the terminal to cooked mode after a synchronous child process exits.
- **`os`, `shutil`, `subprocess`, `sys`, `tempfile`** (stdlib): Provide the concrete host operations.

## Class Invariants
- `stdin_detached_sync`: A synchronous `run_command` passes `stdin=subprocess.DEVNULL`, so a child never blocks on the session input stream.
- `cooked_mode_restore`: A synchronous `run_command` calls `restore_cooked_mode` in a `finally` block, so the TTY survives a misbehaving child.
- `windows_detached_background`: A background launch on Windows sets `CREATE_NO_WINDOW`, so a GUI editor or diff viewer cannot mutate the parent console input mode.
- `temp_file_outlives_process`: `create_temp_file` opens with `delete=False`, so the file survives the creating process.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`ISystemEnvironment`**: The driven contract implemented by this adapter. See the [ISystemEnvironment design](../../core/ports/outbound/system_environment.md).

## Data Contracts
- **`run_command` args:** A non-empty argument list.
- **`create_temp_file` return:** The created file path.

## Operations

### `which(command) -> Optional[str]`
- **Postconditions:** Returns the resolved command path, or `None` when not found.

### `get_env(key) -> Optional[str]`
- **Postconditions:** Returns the environment-variable value, or `None`.

### `isatty() -> bool`
- **Postconditions:** Returns whether a terminal is attached to stdin.

### `run_command(args, check=True, background=False) -> None`
- **Preconditions:** `args` is a non-empty argument list.
- **Postconditions:** Runs the command synchronously and restores cooked mode, or launches it detached when `background` is `True`.

### `create_temp_file(suffix="", mode="w") -> str`
- **Postconditions:** Creates a temporary file with `delete=False` and returns its path.

### `delete_file(path) -> None`
- **Preconditions:** `path` exists.
- **Postconditions:** Deletes the file.
