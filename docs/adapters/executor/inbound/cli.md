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

### Main Command: `execute`
**Status:** Refactoring
**Updated in:** [Slice 19: Unified `execute` Command & Interactive Approval](../../slices/executor/19-unified-execute-command.md)

This is the primary command for executing a plan.

*   **Signature:** `teddy execute [PLAN_FILE] [--yes]`
*   **Input:**
    *   `PLAN_FILE` (Optional): A path to a YAML plan file.
    *   If `PLAN_FILE` is omitted, the command reads the plan from the system clipboard. This introduces a dependency on the `pyperclip` library.
        *   **Dependency Vetting:** The `pyperclip` library was vetted via a technical spike (`spikes/technical/spike_clipboard_access.py`, now deleted) to confirm its cross-platform reliability, in accordance with the project's third-party dependency standards.
    *   `--yes` (Optional Flag): If provided, the plan will be executed in non-interactive mode, automatically approving all actions.
*   **Behavior:**
    1.  Reads the plan content from the specified source (file or clipboard).
    2.  Determines the approval mode (`auto_approve` is `True` if `--yes` is present).
    3.  Calls the `PlanService` via the `RunPlanUseCase` port, passing the plan content and the `auto_approve` flag.
    4.  Prints the final YAML report to standard output.

### Utility Command: `context`
**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

This command provides a comprehensive snapshot of the project for an AI agent.

*   **Input:** This command takes no arguments.
*   **Behavior:** It invokes the `ContextService` via the `IGetContextUseCase` port. It receives a `ContextResult` domain object in return, formats it into a structured, human-readable string, and prints it to standard output.

### Output Handling

#### Plan Execution Report
The `cli_formatter.py` module contains a `format_report_as_yaml` function responsible for converting the `ExecutionReport` domain model into a YAML string. This keeps presentation logic separate from the core application. The formatted report is printed to `stdout`. The application exits with a non-zero status code if any action in the plan fails.

#### Project Context Snapshot
**(Updated in: [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md))**

The `cli_formatter.py` module contains a `format_project_context` function. This function takes the `ContextResult` DTO and renders it as a single string with four distinct sections, in order.

1.  **`# System Information`**: This section is a markdown-formatted list of key-value pairs from the `system_info` attribute of the `ContextResult`. It **MUST** include the `shell` and **MUST NOT** include the `python_version`.

2.  **`# Repository Tree`**: This section contains the verbatim string from the `repo_tree` attribute of the `ContextResult`.

3.  **`# Context Vault`**: This section contains a simple, newline-delimited list of file paths from the `context_vault_paths` attribute. It **MUST NOT** be formatted as a code block.

4.  **`# File Contents`**: This section iterates through the `file_contents` dictionary. For each file, it prints the file path followed by its content enclosed in a markdown code block with the appropriate language extension. For example:
    ```
    path/to/file.py
    `````python
    # Contents of file.py
    print("Hello, World!")
    `````
    ```
