# Inbound Adapter: CLI

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The CLI adapter is the primary entry point for the `teddy` application. It is responsible for:
1.  Parsing user commands and arguments (`teddy execute`, `teddy context`).
2.  Reading plan content for the execution command from a file (`--plan-file`).
3.  Invoking the correct application service via the appropriate inbound port.
4.  Formatting the resulting domain object (`ExecutionReport` or `ProjectContext`) into a user-facing string.
5.  Printing the final output to standard output.

## 2. Used Inbound Ports

This adapter is a "driving" adapter that uses inbound ports to interact with the application core.

*   For plan execution: [`RunPlanUseCase`](../../core/ports/inbound/run_plan_use_case.md)
*   For context gathering: [`IGetContextUseCase`](../../core/ports/inbound/get_context_use_case.md) (**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md))

## 3. Command-Line Interface

*   **Technology:** `Typer`
*   **Composition Root:** The application's dependency injection and wiring are handled in `src/teddy/main.py` and `src/teddy/cli.py`.

### Main Command: `teddy execute`

This is the primary command for executing a plan. It will be the default command if no subcommand is specified.

*   **Input:** The command accepts a plan from a file via the `--plan-file` option. `stdin` is reserved for interactive user input (e.g., for the `chat_with_user` action).
*   **Behavior:** It executes the plan by calling the `PlanService` and prints a machine-readable YAML report to standard output.

### Utility Command: `context`
**Status:** Planned
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

This command provides a comprehensive snapshot of the project for an AI agent.

*   **Input:** This command takes no arguments.
*   **Behavior:** It invokes the `ContextService` via the `IGetContextUseCase` port. It receives a `ProjectContext` domain object in return, formats it into a structured, human-readable string, and prints it to standard output.

### Output Handling

#### Plan Execution Report
The `cli_formatter.py` module contains a `format_report_as_yaml` function responsible for converting the `ExecutionReport` domain model into a YAML string. This keeps presentation logic separate from the core application. The formatted report is printed to `stdout`. The application exits with a non-zero status code if any action in the plan fails.

#### Project Context Snapshot
A new formatter function, `format_project_context`, will be added to `cli_formatter.py`. This function will take the `ProjectContext` object and render it as a single string with clear headings for each section (OS Info, Repo Tree, File Contents, etc.), ready to be consumed by an LLM.
