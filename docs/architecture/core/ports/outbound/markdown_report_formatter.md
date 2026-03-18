**Status:** Planned

## 1. Purpose / Responsibility
Defines the contract for any service that can format an `ExecutionReport` domain object into a final, user-facing Markdown string.

## 2. Ports
This component is an **Outbound Port**. The hexagonal core (specifically the CLI adapter in this case) depends on this interface to delegate the responsibility of presentation formatting.

## 3. Implementation Details
This port is expected to be implemented by a `MarkdownReportFormatter` service.

## 4. Data Contracts / Methods

### `format(self, report: ExecutionReport, is_concise: bool = True) -> str`
-   **Description:** The primary method to execute the formatting process.
-   **Parameters:**
    -   `report`: The `ExecutionReport` object.
    -   `is_concise`: If `True`, generates a concise CLI report. If `False`, generates a comprehensive Session report.
-   **Preconditions:**
    -   `report` must be a valid `ExecutionReport` domain object.
-   **Postconditions:**
    -   Returns a single string containing the report formatted as Markdown.
-   **Invariants:** This method must not cause any side effects.
