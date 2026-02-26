# Service: `MarkdownPlanParser`

**Status:** Implemented
**Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose
The `MarkdownPlanParser` service is responsible for parsing a plan written in the proprietary Markdown format specified in the [New Plan Format Specification](../../specs/new-plan-format.md). It transforms the Markdown text into a valid `Plan` domain object that can be consumed by the `ExecutionOrchestrator`.

## 2. Core Responsibilities
- **AST Parsing:** Uses the `mistletoe` library to parse Markdown into an Abstract Syntax Tree (AST).
- **Structural Validation:** Enforces a strict, top-level document structure (H1 Title -> Metadata List -> Rationale -> optional Memos -> Action Plan) using a single-pass traversal strategy.
- **Action Dispatching:** Iterates through the `## Action Plan` section and dispatches parsing control to specialized strategy functions based on the detected action type.
- **Path Normalization:** Performs centralized normalization of project-relative paths, ensuring cross-platform compatibility.
- **Error Reporting:** Generates high-fidelity error reports, including AST summaries and structural diffs, to provide actionable feedback when a plan deviates from the specification.
- **Pre-processing:** Employs a `FencePreProcessor` to normalize code fence lengths and ensure correct AST generation for nested code blocks.

## 3. Supported Actions
The parser supports the following actions, each with its own parsing strategy:
- `CREATE`: Extracts file path and content.
- `EDIT`: Extracts file path and sequential `FIND`/`REPLACE` pairs.
- `READ`, `PRUNE`: Extracts resource path or URL.
- `EXECUTE`: Extracts command string, environment variables, and expected outcome. It applies a POSIX Pre-Processor to extract `cwd` and `env` from shell directives (`cd`, `export`).
- `RESEARCH`: Extracts multiple web search queries.
- `CHAT_WITH_USER`: Extracts the markdown message to the user.
- `INVOKE`: Extracts the target agent, message, and optional handoff resources.
- `RETURN`: Extracts the completion message and optional handoff resources.

## 4. Modular Architecture
To maintain focus and adhere to file complexity limits, the parser delegates to specialized helper modules:
- **[Parser Infrastructure](./parser_infrastructure.md):** Low-level AST traversal utilities and stream handling (`_PeekableStream`).
- **[Parser Metadata](./parser_metadata.md):** Logic for parsing action metadata lists and message content.
- **[Action Parser Strategies](./action_parser_strategies.md):** The specific grammar and dispatch logic for individual action types.

## 5. Implementation Notes
- **AST Traversal:** A key finding from the initial implementation spike is that `Link` tokens in a metadata list are not direct children of a `ListItem`; the traversal must account for an intermediate `Paragraph` token (`ListItem -> Paragraph -> Link`).
