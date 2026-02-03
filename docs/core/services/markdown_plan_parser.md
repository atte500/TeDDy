# Service: MarkdownPlanParser

**Status:** Implemented

## 1. Responsibilities
- Parses a Markdown plan string into a `Plan` domain object using `mistletoe`.
- Extracts plan metadata (Status, Agent, Goal) from the header.
- Parses action blocks (`### ACTION`) and their specific parameters (metadata list + code blocks).
- Supports atomic multi-edit operations in `EDIT` actions.
- Pre-processes content to fix potential fence nesting issues (via `FencePreProcessor`).

## 2. Collaborators
- **Implements:** `IPlanParser` (Port)
- **Uses:** `mistletoe` (AST Parser Library)
- **Creates:** `Plan`, `ActionData` (Domain Models)

## 3. Supported Actions
- `CREATE`: Extracts content from code block.
- `EDIT`: Extracts `FIND`/`REPLACE` pairs.
- `READ`, `PRUNE`: Extracts resource path.
- `EXECUTE`: Extracts command, env vars, and expected outcome.
- `RESEARCH`: Extracts queries.
- `CHAT_WITH_USER`: Extracts prompt text.
- `INVOKE`: Extracts agent and message.

- **Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose

The `MarkdownPlanParser` service is responsible for parsing a plan written in the proprietary Markdown format specified in the [New Plan Format Specification](../../specs/new-plan-format.md). It transforms the Markdown text into a valid `Plan` domain object that can be consumed by the `ExecutionOrchestrator`.

## 2. Core Responsibilities

1.  **Fence Pre-processing:** Before parsing, the service first runs the raw input string through a `FencePreProcessor` utility. This utility corrects any invalidly nested code block fences (e.g., a ``` fence within another ``` fence), ensuring the Markdown passed to the parser is always valid.
2.  **AST Parsing:** The service uses the `mistletoe` library to parse the corrected Markdown string into an Abstract Syntax Tree (AST).
3.  **AST Traversal:** The service traverses the AST to identify and extract data from the core document sections (`# Plan Header`, `## Rationale`, `## Action Plan`, etc.).
4.  **Action Extraction:** It iterates through the nodes under `## Action Plan` to parse each action block (`### CREATE`, `### EDIT`, etc.), extracting their parameters and content.
5.  **Plan Object Construction:** Finally, it uses the extracted data to construct and return a `Plan` domain object.

## 3. Dependencies

-   **`mistletoe`:** For parsing Markdown into an AST.

## 4. Error Handling

-   If the Markdown structure deviates from the specification (e.g., a missing `#` heading, a malformed action block), the parser will raise a `MarkdownPlanParsingError` with a descriptive message.

## 5. Implementation Notes (from Spike)

The technical spike (`spikes/plumbing/01_mistletoe_parser/`) confirmed the viability of using `mistletoe`. The key finding relates to the AST structure for extracting linked file paths from a metadata list:

-   **Correct Traversal Path:** A `Link` token is not a direct child of a `ListItem`. The correct path to traverse the AST is `ListItem -> Paragraph -> Link`. The parser implementation must account for this intermediate `Paragraph` token to reliably extract link targets.
