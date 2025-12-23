# Inbound Adapter: CLI

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The CLI adapter is the primary entry point for the `teddy` application. It is responsible for:
1.  Reading plan content from a file (`--plan-file`) or standard input (`stdin`).
2.  Invoking the application's core logic via an inbound port.
3.  Formatting the `ExecutionReport` domain object into a pure YAML string.
4.  Printing the final report to standard output.

## 2. Implemented Ports

This adapter is a "driving" adapter that **uses** an inbound port to interact with the application core.

*   **Uses Inbound Port:** [`RunPlanUseCase`](../../core/ports/inbound/run_plan_use_case.md)

## 3. Command-Line Interface

*   **Technology:** `Typer`
*   **Composition Root:** The application's dependency injection and wiring are handled in `src/teddy/main.py`.

### Main Command: `teddy`

This is the primary command for executing a plan.

*   **Input:** The command accepts a plan from a file via the `--plan-file` option. If this option is not provided, it falls back to reading from `stdin`. `stdin` is reserved for interactive user input (e.g., for the `chat_with_user` action).
*   **Behavior:** It executes the plan and prints a machine-readable YAML report to standard output.

### Output Handling

The `cli_formatter.py` module contains a `format_report_as_yaml` function responsible for converting the `ExecutionReport` domain model into a YAML string. This keeps presentation logic separate from the core application. The formatted report is printed to `stdout`. The application exits with a non-zero status code if any action in the plan fails.
