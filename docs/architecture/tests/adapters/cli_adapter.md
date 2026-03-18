# Test Adapter: CliTestAdapter
- **Status:** Refactoring

## 1. Purpose / Responsibility
The `CliTestAdapter` provides a high-level API for driving the TeDDy CLI in an isolated, in-process environment. It encapsulates the use of `typer.testing.CliRunner` and provides "Inverse Adapters" that parse the CLI's Markdown output back into structured DTOs for easy assertion.

## 2. Ports
- **Primary Driving Adapter:** Drives the `CLI Adapter` (Inbound Adapter).
- **Secondary Driven Port:** Uses the `Test Composition` to manage environment isolation (CWD, Monkeypatching).

## 3. Implementation Details / Logic
- **In-Process Execution:** Uses `CliRunner.invoke` to run the `app` object directly, ensuring that mocks registered in the DI container are respected.
- **Output Parsing:** Uses regex-based strategies to extract the `Run Summary` and `Action Log` from the generated Markdown Execution Report.
- **Path Normalization:** Ensures all paths in the output are converted to Posix format to maintain cross-platform test stability.

## 4. Data Contracts / Methods
- `run_cli_command(args: list, cwd: Path, input: str = None) -> Result`: Low-level wrapper for the CLI runner.
- `run_execute_with_plan(plan_content: str, cwd: Path) -> Result`: Specialized command for executing plans using the `--plan-content` bypass.
- `parse_markdown_report(stdout: str) -> dict`: Parses the execution report into a dictionary with keys: `run_summary` and `action_logs`.
