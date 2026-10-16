# Component Design: ShellAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/shell_adapter.py`](/src/teddy_executor/adapters/outbound/shell_adapter.py)

## Purpose
Implements the `IShellExecutor` outbound port. It runs commands through the operating system shell, isolates each child process in its own process group, and returns a structured `ShellOutput` with sanitized, truncated output.

## Consumers
- [`ActionFactory`](../../core/services/action_factory.md): Binds the `execute` method to `EXECUTE` actions.
- [Composition Root](/src/teddy_executor/container.py): Constructs the adapter with the command builder, the output line cap, and the interrupt guard.

## Dependencies
- **`ShellCommandBuilder`** (`teddy_executor.adapters.outbound.shell_command_builder`): Prepares the final command argument list and the shell flag.
- **`InterruptGuard`** (`teddy_executor.core.utils.interrupt_guard`): Optional shared guard polled while a command is in flight.
- **`truncate_lines`** (`teddy_executor.core.utils.string`): Applies the stdout tail cap.

## Class Invariants
- `poll_interval_constant`: `_POLL_INTERVAL_SECONDS` is a module-level code constant (`0.1`), not a configurable setting.
- `timeout_exit_code`: A timed-out command returns exit code `124`.
- `cwd_containment`: A relative `cwd` must resolve inside the project root, otherwise `execute` raises `ValueError`. Absolute paths pass through as explicit user choices.
- `output_sanitization`: Every `stdout` and `stderr` value is stripped of ANSI escape sequences before it is returned.
- `tail_truncation`: `stdout` is truncated at the tail to the effective line cap; `stderr` is never truncated.
- `process_group_isolation`: On POSIX the child runs in its own session (`setsid`), so a terminal SIGINT cannot reach it and a kill reaches the whole command tree.
- `guard_optional`: When no interrupt guard is injected, `execute` keeps the legacy single blocking `communicate` path.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IShellExecutor`**: The driven contract implemented by this adapter. See the [IShellExecutor design](../../core/ports/outbound/shell_executor.md).

## Data Contracts
- **`ShellOutput`** (`TypedDict`): `stdout: str`, `stderr: str`, `return_code: int`, `failed_command: NotRequired[str]`, `interrupted: NotRequired[bool]`. See the [ShellOutput design](../../core/domain/shell_output.md).
- **Configuration key:** `max_execute_lines` sets the default stdout line cap (`100`).

## Operations

### `execute(command, cwd=None, env=None, timeout=None, background=False, max_lines=None) -> ShellOutput`
- **Preconditions:** `command` is a non-empty string; a relative `cwd` resolves inside the project root.
- **Postconditions:** Returns a `ShellOutput`. In background mode it launches a detached process and returns its PID immediately. In synchronous mode it blocks until the child exits, the guard fires, or the timeout elapses. A non-zero exit carries the parsed `FAILED_COMMAND` marker when present, and an interactive-prompt failure is replaced with the standard detection message.
- **Exceptions:** `ValueError` when a relative `cwd` escapes the project root.

### Internal helpers
`_validate_cwd` resolves and containment-checks the working directory. `_await_process` polls the guard between slices or blocks once. `_handle_timeout` kills the process group and returns exit code `124`. `_process_execution_results` sanitizes, truncates, and maps the raw output. `_detect_interactive_prompt` scans both streams for interactive-input patterns.
