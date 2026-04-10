# Bug: Systemic CLI Harness Regression (ValueError: stderr not separately captured)

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

121 tests are failing across acceptance and integration suites with the following error:
`ValueError: stderr not separately captured` at `tests/harness/drivers/cli_adapter.py:36`.

This occurs when `CliTestAdapter.run_cli_command` attempts to access `result.stderr` from a `click.testing.Result` object.

## System Model

### Understanding
The `CliTestAdapter` uses `typer.testing.CliRunner` (which wraps `click.testing.CliRunner`) to drive the application in tests.
1. By default, `CliRunner` mixes stdout and stderr.
2. Accessing the `result.stderr` property when mixed triggers a `ValueError`.
3. The `click.testing.Result.stderr` property is read-only; attempts to assign to it (e.g., `result.stderr = ""`) will fail even if capture was enabled.
4. The harness currently initializes `CliRunner()` without arguments and then attempts to both read and write to `result.stderr`.

### Discrepancies
None.

## Solution

### Implemented Fixes
- Configured `typer.testing.CliRunner(mix_stderr=False)` in `CliTestAdapter.__init__` to ensure stderr is captured separately and accessible via the `result.stderr` property.
- Removed invalid assignment `result.stderr = ""` in `run_cli_command`, as `result.stderr` is a read-only property.

### Prevention
- The test harness is now aligned with the `click.testing` API contract.
- Future harness changes should be verified with a minimal probe if they involve third-party test utilities.
