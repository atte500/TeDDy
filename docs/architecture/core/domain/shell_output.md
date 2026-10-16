# Component Design: ShellOutput
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/domain/models/shell_output.py`](/src/teddy_executor/core/domain/models/shell_output.py)

## Purpose
A strictly-typed `TypedDict` that standardizes the result of any shell command executed through the `IShellExecutor` port. It replaced the legacy `CommandResult` dataclass to improve type safety.

## Consumers
- [`IShellExecutor`](../ports/outbound/shell_executor.md): Declares `ShellOutput` as its return type.
- [ShellAdapter](../../adapters/outbound/shell_adapter.md): Populates the DTO from subprocess results.
- [`ActionDispatcher`](../services/action_dispatcher.md): Reads `interrupted` to mark an action `INTERRUPTED`.

## Dependencies
None — this is a passive data structure.

## Class Invariants
- `required_keys`: `stdout`, `stderr`, and `return_code` are required keys.
- `optional_keys`: `failed_command` and `interrupted` are `NotRequired`.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
None — this is a passive data structure.

## Data Contracts
- **`ShellOutput`** (`TypedDict`): `stdout: str`, `stderr: str`, `return_code: int`, `failed_command: NotRequired[str]`, `interrupted: NotRequired[bool]`.

## Operations
None — this component holds data only.
