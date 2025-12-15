# Inbound Adapter: CLI

**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The CLI adapter is the main entry point for the `teddy` application. It is responsible for handling command-line arguments, reading input from the user (initially from stdin), invoking the application core, and displaying the final report to the user.

## 2. Implemented Ports

This adapter doesn't directly implement a port, but it is a "driving" adapter that **uses** an inbound port.

*   **Uses Inbound Port:** [`RunPlanUseCase`](../../core/ports/inbound/run_plan_use_case.md)

## 3. Implementation Notes

*   **Technology:** The CLI will be built using the `Typer` library.
*   **Entry Point:** The main application object will be in `src/teddy/main.py`. This file will also handle the composition of the application layers (dependency injection).
*   **Dependencies:** The CLI will depend on the `PlanService` (the implementation of the `RunPlanUseCase`).

### Composition Root (Dependency Injection)

The `main.py` file will act as the **Composition Root**. It is responsible for instantiating all the components and "wiring" them together.

```python
# Conceptual wiring in src/teddy/main.py
import sys
import typer
from typing import cast
# ... other imports

# 1. The Typer application object is defined
app = typer.Typer()

# 2. A callback function contains the core application logic
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    # The PlanService is retrieved from the context
    plan_service = cast(RunPlanUseCase, ctx.obj)
    plan_content = sys.stdin.read()

    # The use case is invoked
    report = plan_service.execute(plan_content)

    # The report is formatted and printed
    formatted_report = format_report_as_markdown(report)
    typer.echo(formatted_report)

    # The exit code is set based on the report's status
    if report.run_summary.get("status") == "FAILURE":
        raise typer.Exit(code=1)

# 3. A `run()` function acts as the Composition Root
def run():
    # Adapters and services are instantiated here
    shell_adapter = ShellAdapter()
    # ... other adapters
    plan_service = PlanService(...)

    # The Typer app is run with the composed service object
    app(obj=plan_service)
```

### Input Handling (Walking Skeleton)

*   For this slice, the application will read from `sys.stdin` until EOF. It will not handle file-based input or interactive mode yet.

### Output Handling (Walking Skeleton)

*   A private function `_format_report_as_markdown` will be created within this adapter. It will take the `ExecutionReport` domain object and convert it into a human-readable Markdown string, which is then printed to standard output. This keeps the domain object clean of presentation logic.

## 4. Related Spikes

*   This component's design is informed by the initial public contract defined in `README.md` and the various functional spikes that clarified the tool's behavior.
