# Inbound Adapter: CLI

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

> [!WARNING]
> **Documentation Discrepancy Found:** The current implementation in `src/teddy/main.py` only supports the main plan execution via `stdin`. The utility commands (`context`, `copy-unstaged`) and the non-interactive flag (`-y`) described in `README.md` are not present in the provided source code. This document has been updated to reflect the *actual* implementation.

## 1. Purpose

The CLI adapter is the primary entry point for the `teddy` application. It is responsible for:
1.  Reading plan content from standard input (`stdin`).
2.  Invoking the application's core logic via an inbound port.
3.  Formatting the `ExecutionReport` domain object into a user-friendly markdown string.
4.  Printing the final report to standard output.

## 2. Implemented Ports

This adapter is a "driving" adapter that **uses** an inbound port to interact with the application core.

*   **Uses Inbound Port:** [`RunPlanUseCase`](../../core/ports/inbound/run_plan_use_case.md)

## 3. Command-Line Interface

*   **Technology:** `Typer`
*   **Composition Root:** The application's dependency injection and wiring are handled in `src/teddy/main.py`.

### Main Command: `teddy`

This is the primary command for executing a plan.

*   **Input:** The command reads a YAML plan from `stdin`. It does not accept a file path as a direct argument. This allows for flexible piping from files (`cat plan.yml | teddy`) or other commands.
*   **Behavior:** It executes the plan and prints a report to standard output. Based on the provided source, interactive approval is not implemented; it executes the plan directly.

### Output Handling

A `CLIFormatter` class is responsible for converting the `ExecutionReport` domain model into a markdown string. This keeps presentation logic separate from the core application. The formatted report is printed to `stdout`. The application exits with a non-zero status code if any action in the plan fails.
