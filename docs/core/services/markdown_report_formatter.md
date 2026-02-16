**Status:** Implemented
**Introduced in:** [Slice 01: Markdown Report Generator](../../slices/01-markdown-report-generator.md)

## 1. Purpose / Responsibility
To implement the `IMarkdownReportFormatter` outbound port. This service uses the Jinja2 templating engine to render an `ExecutionReport` object into a Markdown string suitable for CLI output.

## 2. Ports
-   **Implements (Outbound):** `IMarkdownReportFormatter`

## 3. Implementation Details
This service will be implemented using the **Jinja2 Template Engine**, as validated by the technical spike.

1.  **Template Loading:** The service will be initialized with a Jinja2 `Environment`. It will be configured to load templates from a dedicated directory within the project's source code (e.g., `src/teddy_executor/core/services/templates/`).
2.  **Context Preparation:** The `format` method will receive an `ExecutionReport` object. It will transform this object into a simple dictionary (`context`) that is easy to work with inside the Jinja2 template. This separates the domain model from the presentation context.
3.  **Rendering:** The `format` method will load a specific template (e.g., `concise_report.md.j2`), render it with the prepared context, and return the resulting string.

This approach provides a clean separation of concerns between data preparation (Python) and presentation (the template file).

## 4. Data Contracts / Methods
This service implements the `format` method as defined by the `IMarkdownReportFormatter` port.
