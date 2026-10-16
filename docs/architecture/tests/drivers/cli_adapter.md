# Component Design: CliTestAdapter
- **Status:** Implemented
- **Source:** [`tests/harness/drivers/cli_adapter.py`](/tests/harness/drivers/cli_adapter.py)

## Purpose
A test-harness driver that runs the TeDDy CLI in-process and returns structured results. It is the primary driving adapter of the Test Harness Triad, wrapping `typer.testing.CliRunner` and normalizing console output for assertion.

## Consumers
- Acceptance and integration test suites: Drive the CLI in-process and assert on the returned `Result` or the parsed `ReportParser`.

## Dependencies
- **`CliRunner`** (`typer.testing`, external): Invokes the CLI `app` in-process.
- **`app`** (`teddy_executor.__main__`): The CLI entry point invoked by the runner.
- [`ReportParser`](../observers/report_parser.md): Parses the combined stdout and stderr into structured data.

## Class Invariants
- `in_process_invocation`: Every command runs through `CliRunner.invoke`, so a test-configured DI container is respected.
- `ansi_normalized_output`: `run_cli_command` strips ANSI escape sequences from `Result.stdout` before returning it.
- `editor_mock_env`: When `set_mock_editor_output` has been called, the command environment carries `TEDDY_TEST_MOCK_EDITOR_OUTPUT`.

## Inbound Ports
None — this is a test harness component.

## Outbound Ports
None — this is a test harness component.

## Data Contracts
- **`Result`** (`typer.testing`): The CLI invocation result carrying `stdout`, `stderr`, `exit_code`, and `exception`.
- **`ReportParser`**: The structured observer returned by `execute_plan`.

## Operations

### `CliTestAdapter(monkeypatch, cwd)`
- **Postconditions:** Stores the `CliRunner`, the monkeypatch handle, and the default working directory.

### `set_mock_editor_output(content) -> None`
- **Postconditions:** Sets the content the mocked external editor returns on the next command.

### `run_cli_command(args, cwd=None, input=None) -> Result`
- **Preconditions:** `args` is a list of CLI arguments.
- **Postconditions:** Runs the command in `cwd` or the default directory and returns the `Result` with ANSI-free `stdout`.

### `run_execute_with_plan(plan_content, cwd=None, input=None, interactive=False, extra_args=None) -> Result`
- **Postconditions:** Runs `execute --no-copy --plan-content <plan_content>`, appending `--yolo` when `interactive` is `False` and any `extra_args` after it.

### `run_start(args, input=None) -> Result`
- **Postconditions:** Runs the `start` command with the supplied arguments.

### `run_resume(path=None, no_copy=True, interactive=True, input=None, extra_args=None) -> Result`
- **Postconditions:** Runs the `resume` command with the supplied path and flags.

### `execute_plan(plan_content, user_input=None, interactive=False, extra_args=None) -> ReportParser`
- **Postconditions:** Runs the plan, re-raises any exception that is not a `SystemExit` or `click.exceptions.Exit`, and returns a `ReportParser` over the combined stdout and stderr.

### `run_command(args, input=None) -> Result`
- **Postconditions:** Legacy alias for `run_cli_command`.

### Internal helpers
`_strip_ansi` removes ANSI escape sequences from captured output.
