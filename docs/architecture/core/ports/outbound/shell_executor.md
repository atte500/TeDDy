# Component Design: IShellExecutor
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/shell_executor.py`](/src/teddy_executor/core/ports/outbound/shell_executor.py)

## Purpose
Defines the outbound port for executing shell commands. It lets the core run commands and capture structured output without depending on `subprocess` or the operating system.

## Consumers
- [`ActionFactory`](../../services/action_factory.md): Builds `EXECUTE` actions that call the port.

## Dependencies
- **`ShellOutput`** (`teddy_executor.core.domain.models.shell_output`): The return type.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations override `execute`.
- `always_returns_output`: `execute` always returns a `ShellOutput`; command failures are carried in `return_code` and `stderr`, not raised.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IShellExecutor`**: The driven contract consumed by the action layer and implemented by the `ShellAdapter`.

## Data Contracts
- **`ShellOutput`** (`TypedDict`): `stdout: str`, `stderr: str`, `return_code: int`, `failed_command: NotRequired[str]`, `interrupted: NotRequired[bool]`.

## Operations

### `execute(command, cwd=None, env=None, timeout=None, background=False, max_lines=None) -> ShellOutput`
- **Preconditions:** `command` is a non-empty string; `cwd`, when given, is a project-relative path.
- **Postconditions:** Returns a `ShellOutput`; blocks until completion unless `background` is `True`, in which case it returns immediately after launching.
- **Exceptions:** `ValueError` when `cwd` is absolute or escapes the project directory.
