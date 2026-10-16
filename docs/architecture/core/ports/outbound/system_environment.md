# Component Design: ISystemEnvironment
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/system_environment.py`](/src/teddy_executor/core/ports/outbound/system_environment.py)

## Purpose
Defines the outbound port for host operating-system interactions: locating commands, reading environment variables, running external processes, and managing temporary files. It keeps adapters pure and testable.

## Consumers
- [`ConsoleTooling`](../../../adapters/outbound/console_tooling.md): Discovers editors and diff viewers on `PATH`.
- [`ConsoleInteractor`](../../../adapters/outbound/console_interactor.md): Launches the editor and diff tools.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `protocol_contract`: The port is a `Protocol`; implementing adapters satisfy the structural contract.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`ISystemEnvironment`**: The driven contract consumed by outbound adapters and implemented by the `SystemEnvironmentAdapter`.

## Data Contracts
- **`create_temp_file` return:** the created file path.

## Operations

### `which(command) -> Optional[str]`
- **Preconditions:** None.
- **Postconditions:** Returns the resolved command path, or `None` when not found.

### `get_env(key) -> Optional[str]`
- **Preconditions:** None.
- **Postconditions:** Returns the environment-variable value, or `None`.

### `run_command(args, check=True, background=False) -> None`
- **Preconditions:** `args` is a non-empty argument list.
- **Postconditions:** Runs the command synchronously, or in the background when `background` is `True`.

### `create_temp_file(suffix="", mode="w") -> str`
- **Preconditions:** None.
- **Postconditions:** Creates a temporary file and returns its path.

### `delete_file(path) -> None`
- **Preconditions:** `path` exists.
- **Postconditions:** Deletes the file.

### `isatty() -> bool`
- **Preconditions:** None.
- **Postconditions:** Returns whether a terminal is attached to stdin.
