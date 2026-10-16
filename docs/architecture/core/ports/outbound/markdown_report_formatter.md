# Component Design: IMarkdownReportFormatter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/markdown_report_formatter.py`](/src/teddy_executor/core/ports/outbound/markdown_report_formatter.py)

## Purpose
Defines the outbound port for rendering an `ExecutionReport` into a user-facing Markdown string. It isolates presentation formatting from the core so the report layout can change without touching the orchestrator.

## Consumers
- [`ExecutionOrchestrator`](../../services/execution_orchestrator.md): Renders the report for display and persistence.
- [CLI Adapter](../../../adapters/inbound/cli.md): Prints the formatted report.

## Dependencies
- **`ExecutionReport`** (`teddy_executor.core.domain.models`): The rendered model.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations override `format`.
- `side_effect_free`: `format` must not mutate the report or the filesystem.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IMarkdownReportFormatter`**: The driven contract consumed by the orchestrator and implemented by the `MarkdownReportFormatter` service.

## Data Contracts
- **`ExecutionReport`** (`teddy_executor.core.domain.models.execution_report`): The report to render.

## Operations

### `format(report) -> str`
- **Preconditions:** `report` is a valid `ExecutionReport`.
- **Postconditions:** Returns the report as a single Markdown string.
