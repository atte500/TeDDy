# Service: MarkdownPlanParser

**Status:** Implemented

## 1. Responsibilities
- Parses a Markdown plan string into a `Plan` domain object using `mistletoe`.
- Strictly validates action headers against the `ActionType` enum, rejecting unknown actions (even if formatted as code blocks).
- Performs centralized path normalization, converting Windows backslashes to POSIX forward slashes for cross-platform compatibility.
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
- `RETURN`: Extracts message and handoff resources.

- **Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose

The `MarkdownPlanParser` service is responsible for parsing a plan written in the proprietary Markdown format specified in the [New Plan Format Specification](../../specs/new-plan-format.md). It transforms the Markdown text into a valid `Plan` domain object that can be consumed by the `ExecutionOrchestrator`.

## 2. Core Responsibilities

1.  **Fence Pre-processing:** Before parsing, the service first runs the raw input string through a `FencePreProcessor` utility. This utility corrects any invalidly nested code block fences (e.g., a ``` fence within another ``` fence), ensuring the Markdown passed to the parser is always valid.
2.  **Stream Wrapping:** The service wraps the `mistletoe` AST's top-level children in a `PeekableStream` iterator, allowing lookahead traversal.
3.  **Single-Pass Dispatch Loop:** The parser iterates through the stream.
    *   **Action Detection:** When it encounters a Level 3 `Heading` that matches a known `ActionType` (e.g., `### CREATE`), it dispatches control to the corresponding private handler (e.g., `_parse_create_action`).
    *   **Robustness (The "Ignore" Policy):** Any node that is *not* a recognized Action Heading (including `ThematicBreak`, `Paragraph`, or unknown headings) is simply consumed and ignored. This allows the parser to gracefully handle separators, comments, or malformed content between actions without crashing.
4.  **Specific Parsers:** Each handler consumes nodes from the stream to build the `ActionData` object. They enforce the internal grammar of the action (e.g., `CREATE` must have a Metadata List followed by a Code Block).
5.  **Text Extraction:** A `_get_text(node)` helper recursively extracts text from `mistletoe` tokens, handling the nested structure of `InlineCode` and `RawText` nodes correctly.

## 3. Dependencies

-   **`mistletoe`:** For parsing Markdown into an AST.

## 4. Error Handling

-   If the Markdown structure deviates from the specification (e.g., a missing `#` heading, a malformed action block), the parser will raise a `MarkdownPlanParsingError` with a descriptive message.

## 5. Implementation Notes (from Spike)

The technical spike (`spikes/plumbing/01_mistletoe_parser/`) confirmed the viability of using `mistletoe`. The key finding relates to the AST structure for extracting linked file paths from a metadata list:

-   **Correct Traversal Path:** A `Link` token is not a direct child of a `ListItem`. The correct path to traverse the AST is `ListItem -> Paragraph -> Link`. The parser implementation must account for this intermediate `Paragraph` token to reliably extract link targets.
