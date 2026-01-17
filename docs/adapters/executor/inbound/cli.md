# Inbound Adapter: CLI

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:** [Slice 01: Walking Skeleton](../../../slices/executor/01-walking-skeleton.md)

## 1. Dependency Injection & Composition Root

**Status:** Planned

To address the complexity in the composition root and decouple the CLI commands from concrete service implementations, we will use a Dependency Injection (DI) container. This is a central part of the [Comprehensive Refactoring Brief](../../../briefs/01-comprehensive-refactoring.md).

-   **Library:** `punq`
-   **Strategy:** A single DI container will be initialized at application startup in `packages/executor/src/teddy_executor/main.py`. It will be responsible for instantiating and wiring all services, adapters, and their dependencies. CLI command functions will then resolve the top-level use case (`ExecutionOrchestrator`) from this container.

### Example Composition Root (`main.py`)

```python
import punq
import typer

# Import services, ports, and adapters
from teddy_executor.core.services import (
    ExecutionOrchestrator,
    PlanParser,
    ActionDispatcher,
    ActionFactory
)
from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    IUserInteractor
)
from teddy_executor.adapters.outbound import (
    LocalFileSystemAdapter,
    ConsoleInteractorAdapter
)

def create_container() -> punq.Container:
    """Initializes and configures the DI container."""
    container = punq.Container()

    # Register outbound adapters (implementations)
    container.register(IFileSystemManager, LocalFileSystemAdapter)
    container.register(IUserInteractor, ConsoleInteractorAdapter)

    # Register application services
    container.register(ActionFactory)
    container.register(PlanParser)
    container.register(ActionDispatcher)
    container.register(ExecutionOrchestrator)

    return container

# Create the application instance and container
app = typer.Typer()
container = create_container()

@app.command()
def execute(
    # ... typer options ...
):
    """Executes a plan."""
    # Resolve the main service from the container
    orchestrator = container.resolve(ExecutionOrchestrator)

    # Call the service
    report = orchestrator.execute(plan_path=..., interactive=...)
    # ... format and print report ...
```

## 2. Purpose

The CLI adapter is the primary entry point for the `teddy` application. It is responsible for:
1.  Parsing user commands and arguments (`teddy execute`, `teddy context`).
2.  Reading plan content for the execution command from a positional file argument or the clipboard.
3.  Invoking the correct application service via the appropriate inbound port (resolved from the DI container).
4.  Formatting the resulting domain object (`ExecutionReport` or `ProjectContext`) into a user-facing string.
5.  Printing the final output to standard output.

## 3. Used Inbound Ports

This adapter is a "driving" adapter that uses inbound ports to interact with the application core.

*   For plan execution: [`RunPlanUseCase`](../../../contexts/executor/ports/inbound/run_plan_use_case.md), implemented by the `ExecutionOrchestrator` service.
*   For context gathering: [`IGetContextUseCase`](../../../contexts/executor/ports/inbound/get_context_use_case.md) (**Introduced in:** [Slice 13: Implement `context` Command](../../../slices/executor/13-context-command.md))

## 4. Command-Line Interface

*   **Technology:** `Typer`
*   **Composition Root:** The application's dependency injection and wiring are handled in `packages/executor/src/teddy_executor/main.py` as described in the Dependency Injection section above.

### Main Command: `execute`
**Status:** Implemented
**Updated in:** [Slice 19: Unified `execute` Command & Interactive Approval](../../../slices/executor/19-unified-execute-command.md)

This is the primary command for executing a plan.

*   **Signature:** `teddy execute [PLAN_FILE] [--yes] [--no-copy]`
*   **Input:**
    *   `PLAN_FILE` (Positional Argument, Optional): A path to a YAML plan file.
    *   If `PLAN_FILE` is omitted, the command reads the plan from the system clipboard. This introduces a dependency on the `pyperclip` library.
        *   **Dependency Vetting:** The `pyperclip` library was vetted via a technical spike (`spikes/technical/spike_clipboard_access.py`, now deleted) to confirm its cross-platform reliability, in accordance with the project's third-party dependency standards.
    *   `--yes` (Optional Flag): If provided, the plan will be executed in non-interactive mode, automatically approving all actions.
*   **Behavior (Post-Refactoring):**
    1.  The `typer` command function resolves the `ExecutionOrchestrator` service from the DI container.
    2.  It invokes the `orchestrator.execute()` method, passing the `plan_path` and a boolean `interactive` flag (which is `False` if `--yes` is present).
    3.  It receives the `ExecutionReport` domain model in return.
    4.  It passes the report to a formatter and prints the final YAML report to standard output and the clipboard.

### Utility Command: `context`
**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../../slices/executor/13-context-command.md)

This command provides a comprehensive snapshot of the project for an AI agent.

*   **Input:**
    *   `--no-copy` (Optional Flag): If provided, suppresses the default behavior of copying the output to the system clipboard.
*   **Behavior:** It invokes the `ContextService` via the `IGetContextUseCase` port. It receives a `ContextResult` domain object in return, formats it into a structured, human-readable string, and prints it to standard output while also copying it to the clipboard, as per the standard output handling rules.

### Standard Output Handling
**Updated in:** [Slice 22: Generalized Clipboard Output](../../../slices/executor/22-generalized-clipboard-output.md)

To streamline the interactive user workflow, commands that produce substantial text output (like `context` and `execute`) follow a standard behavior, encapsulated in a private helper function within `main.py`:

1.  The primary output (e.g., project context or execution report) is always printed to `stdout`.
2.  By default, the same output is also copied to the system clipboard using the `pyperclip` library. A confirmation message is printed to `stderr`.
3.  This clipboard behavior is suppressed if the `--no-copy` flag is provided.
4.  If the clipboard is unavailable (e.g., in a headless CI environment), the copy action is silently skipped.

The application exits with a non-zero status code if any action in the `execute` plan fails.

#### Project Context Snapshot
**(Updated in: [Slice 17: Refactor `context` Command Output](../../../slices/executor/17-refactor-context-command-output.md))**

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
