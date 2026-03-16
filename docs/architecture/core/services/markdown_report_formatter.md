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
3.  **Rendering:** The `format` method will load a specific template (e.g., `execution_report.md.j2`), render it with the prepared context, and return the resulting string.

This approach provides a clean separation of concerns between data preparation (Python) and presentation (the template file).

## 5. Responsibilities
-   **Multi-Modal Reporting:** Supports two primary output modes:
    -   **Concise (CLI):** Focuses on immediate outcomes and resource contents. Omits rationale and original action plan to save space and reduce noise in manual workflows.
    -   **Comprehensive (Session):** Provides a full audit trail including rationale and the original action plan. Omits verbatim content of successful `READ` actions (as these are managed by the session's context system).
-   **Modular Rendering:** Uses Jinja2 macros to encapsulate rendering logic for headers, rationales, and action logs, ensuring consistency across modes.
-   **Execution Reporting:** Formats the results of successful or failed actions. Includes the `Similarity Score` for all `EDIT` actions to maintain transparency.
-   **Diff Transparency:** Automatically injects surgical, hunk-based character-level diffs for all successful `EDIT` actions where the `Similarity Score` is less than 1.0, and unified diffs for `CREATE` actions where `Overwrite: true`. Diff injection is suppressed for perfect (1.0) `EDIT` matches.
-   **Validation Reporting:** Renders `validation_result` errors and `failed_resources` (content of files that failed validation) to aid in debugging.
-   **Smart Fencing:** Uses a custom Jinja2 filter (`| fence`) to ensure that code blocks nested within the report (e.g., file content containing backticks) are wrapped in fences with a sufficient number of backticks to remain valid Markdown.
-   **Whitespace Sanitization:** Post-processes the rendered report to remove trailing whitespace and collapse sequences of 3+ newlines into 2. This logic is **code-block aware**, ensuring that whitespace and newlines inside fenced code blocks are preserved verbatim.

## 4. Data Contracts / Methods
This service implements the `format` method as defined by the `IMarkdownReportFormatter` port.
