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
- `EXECUTE`: Extracts command, env vars, and expected outcome. Also applies a POSIX Pre-Processor to the command string to extract `cwd` and `env` from shell directives (`cd`, `export`).
- `RESEARCH`: Extracts queries.
- `CHAT_WITH_USER`: Extracts prompt text.
- `INVOKE`: Extracts agent and message.
- `RETURN`: Extracts message and handoff resources.

- **Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose

The `MarkdownPlanParser` service is responsible for parsing a plan written in the proprietary Markdown format specified in the [New Plan Format Specification](../../specs/new-plan-format.md). It transforms the Markdown text into a valid `Plan` domain object that can be consumed by the `ExecutionOrchestrator`.

## 2. Core Responsibilities

1.  **Orchestration:** The service acts as the entry point for parsing, coordinating the document-level structure validation and delegating action-specific logic.
2.  **Structural Validation:** Validates the overall document structure (H1 Title -> Metadata List -> Rationale -> optional Memos -> Action Plan). It uses a lookahead strategy via `_PeekableStream` to ensure the document strictly follows the specification.
3.  **Dispatching:** Iterates through the nodes in the `## Action Plan` section and dispatches parsing control to specialized strategy functions in the `action_parser_strategies` module based on the detected action type.
4.  **Error Reporting:** When structural violations are detected, it generates a high-fidelity "AST Diff" providing clear feedback on the discrepancy between the expected and actual document structure.

## 3. Delegation & Helpers

To maintain modularity and adhere to file length limits, the parser delegates to the following helper modules:
- **[Parser Infrastructure](./parser_infrastructure.md):** Provides the `_PeekableStream`, `_FencePreProcessor`, and low-level AST traversal utilities.
- **[Action Parser Strategies](./action_parser_strategies.md):** Implements the logic for parsing individual actions and their metadata.

## 3. Dependencies

-   **`mistletoe`:** For parsing Markdown into an AST.

## 4. Error Handling

-   If the Markdown structure deviates from the specification (e.g., a missing `#` heading, a malformed action block), the parser will raise a `MarkdownPlanParsingError` with a descriptive message.

## 5. Implementation Notes (from Spike)

The technical spike (`spikes/plumbing/01_mistletoe_parser/`) confirmed the viability of using `mistletoe`. The key finding relates to the AST structure for extracting linked file paths from a metadata list:

-   **Correct Traversal Path:** A `Link` token is not a direct child of a `ListItem`. The correct path to traverse the AST is `ListItem -> Paragraph -> Link`. The parser implementation must account for this intermediate `Paragraph` token to reliably extract link targets.
