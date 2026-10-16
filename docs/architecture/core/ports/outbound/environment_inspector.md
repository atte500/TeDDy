# Component Design: IEnvironmentInspector
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/environment_inspector.py`](/src/teddy_executor/core/ports/outbound/environment_inspector.py)

## Purpose
Defines the outbound port for gathering information about the host environment, such as the operating system, Python version, shell, and Git status. It decouples context gathering from the concrete platform APIs.

## Consumers
- [`ContextService`](../../services/context_service.md): Gathers environment details and Git status during context assembly.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `protocol_contract`: The port is a `Protocol`; implementing adapters satisfy the structural contract without inheriting from it.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IEnvironmentInspector`**: The driven contract consumed by core services and implemented by the `SystemEnvironmentInspector` adapter.

## Data Contracts
- **`get_environment_info` mapping:** `os_name`, `os_version`, `python_version`, `cwd`, `shell`, `current_date` (YYYY-MM-DD), `current_time` (HH:MM:SS).

## Operations

### `get_environment_info() -> dict[str, str]`
- **Preconditions:** None.
- **Postconditions:** Returns a mapping of environment property names to their string values.

### `get_git_status() -> Optional[str]`
- **Preconditions:** None.
- **Postconditions:** Returns the short-format `git status -s` output, or `None` when the directory is not a Git repository.

### `get_full_git_status() -> Optional[str]`
- **Preconditions:** None.
- **Postconditions:** Returns the full `git status` output including branch information, or `None` when the directory is not a Git repository.
