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

import typer
from teddy.core.services import PlanService
from teddy.adapters.outbound import ShellAdapter

def main():
    # 1. Instantiate adapters
    shell_adapter = ShellAdapter()

    # 2. Instantiate core service with its dependencies
    plan_service = PlanService(shell_executor=shell_adapter)

    # 3. Read input from stdin
    plan_content = sys.stdin.read()

    # 4. Invoke the use case
    report = plan_service.execute(plan_content)

    # 5. Format and print the report
    formatted_report = format_report_as_markdown(report)
    print(formatted_report)

if __name__ == "__main__":
    typer.run(main)
```

### Input Handling (Walking Skeleton)

*   For this slice, the application will read from `sys.stdin` until EOF. It will not handle file-based input or interactive mode yet.

### Output Handling (Walking Skeleton)

*   A private function `_format_report_as_markdown` will be created within this adapter. It will take the `ExecutionReport` domain object and convert it into a human-readable Markdown string, which is then printed to standard output. This keeps the domain object clean of presentation logic.

## 4. Related Spikes

*   This component's design is informed by the initial public contract defined in `README.md` and the various functional spikes that clarified the tool's behavior.
