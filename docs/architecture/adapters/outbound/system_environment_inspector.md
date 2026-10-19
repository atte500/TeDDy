# Component Design: SystemEnvironmentInspector
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/system_environment_inspector.py`](/src/teddy_executor/adapters/outbound/system_environment_inspector.py)

## Purpose
Implements the `IEnvironmentInspector` outbound port with the Python standard library. It reports host properties and the Git working-tree status for the context payload.

## Consumers
- [`ContextService`](../../core/services/context_service.md): Gathers environment details and Git status during context assembly.

## Dependencies
- **`subprocess.run`** (stdlib): Executes the `git status` commands; the callable is injectable for tests.
- **`os`, `platform`, `sys`, `datetime`** (stdlib): Read the host properties.

## Class Invariants
- `injectable_run_func`: The `run_func` constructor argument defaults to `subprocess.run`, so tests substitute a fake runner.
- `cross_platform_shell`: Shell detection returns `$SHELL` on Unix, falls back to `$COMSPEC` on Windows, then returns `"unknown"`.
- `git_status_absent_safe`: `get_git_status` returns `None` when Git is missing or the directory is not a repository.
- `stdin_detached`: Every Git command passes `stdin=subprocess.DEVNULL`.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IEnvironmentInspector`**: The driven contract implemented by this adapter. See the [IEnvironmentInspector design](../../core/ports/outbound/environment_inspector.md).

## Data Contracts
- **`get_environment_info` mapping:** `os_name`, `os_version`, `python_version`, `cwd`, `shell`, `current_date` (YYYY-MM-DD), `current_time` (HH:MM:SS).

## Operations

### `get_environment_info() -> dict[str, str]`
- **Postconditions:** Returns the host property mapping, including the resolved shell and the current date and time.

### `get_git_status() -> Optional[str]`
- **Postconditions:** Returns the `git status --porcelain -b` output, or `None` when the directory is not a Git repository.

### Internal helpers
`_detect_shell` resolves the shell with the cross-platform fallbacks.
