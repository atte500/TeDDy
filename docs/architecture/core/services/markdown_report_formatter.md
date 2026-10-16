# Component Design: MarkdownReportFormatter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/markdown_report_formatter.py`](/src/teddy_executor/core/services/markdown_report_formatter.py)

## Purpose
Implements the `IMarkdownReportFormatter` outbound port. It renders an `ExecutionReport` into a user-facing Markdown string through a cached Jinja2 environment and the `execution_report.md.j2` template, then sanitizes trailing whitespace outside code fences.

## Consumers
- `SessionLifecycleManager` (`session_lifecycle_manager.py`): Renders the report for a session turn. This service has no component doc yet.
- [`SessionPorts`](/src/teddy_executor/core/domain/models/planning_ports.py): Declares `report_formatter: IMarkdownReportFormatter` in the session ports bundle.
- [CLI Adapter](../../adapters/inbound/cli.md): Renders the report for the manual `execute` flow through `cli_helpers`.
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): Renders a synthetic single-action report for the reviewer echo.
- [Composition Root](/src/teddy_executor/container.py): Registers `MarkdownReportFormatter` against `IMarkdownReportFormatter`.

## Dependencies
- `jinja2` (external): Supplies the `Environment` and `PackageLoader` used to render the template.
- [`execution_report.md.j2`](/src/teddy_executor/core/services/templates/execution_report.md.j2): The Jinja2 template that defines the report layout and macros.
- [`embed_in_fence` and `get_language_from_path`](/src/teddy_executor/core/utils/markdown.py): Custom filters for fence-safe content embedding.
- [`scrub_dict_for_serialization`](/src/teddy_executor/core/utils/serialization.py): Neutralizes non-serializable values before rendering.

## Class Invariants
- `cached_environment`: The Jinja2 `Environment` and template are cached at class level and shared across instances.
- `fence_aware_sanitization`: Trailing-whitespace and blank-line sanitization never alters content inside a fenced code block.
- `no_autoescape`: The environment disables autoescape because the output is Markdown, not HTML.

## Inbound Ports
None — this is a concrete implementation of an outbound port.

## Outbound Ports
- **`IMarkdownReportFormatter`**: The driven contract implemented by this service. See the [IMarkdownReportFormatter design](../ports/outbound/markdown_report_formatter.md).

## Data Contracts
- **`ExecutionReport`** (`teddy_executor.core.domain.models.execution_report`): The report rendered into Markdown.

## Operations

### `format(report) -> str`
- **Preconditions:** `report` is a valid `ExecutionReport`.
- **Postconditions:** Returns the rendered Markdown string. The shared template renders two modes: a concise CLI mode that omits the rationale and the original plan, and a comprehensive session mode that carries the full audit trail without verbatim `READ` content. Successful `EDIT` actions with a similarity below 1.0 receive a character-level diff, and overwriting `CREATE` actions receive a unified diff. Fenced content is wrapped through the fence-aware `embed_fence` filter, and trailing whitespace outside code fences is removed.
