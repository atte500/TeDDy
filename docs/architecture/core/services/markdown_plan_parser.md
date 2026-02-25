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

1.  **Fence Pre-processing:** Before parsing, the service runs the raw input string through a `FencePreProcessor` utility to ensure structural validity.
2.  **Stream Wrapping:** The service wraps the `mistletoe` AST's top-level children in a `PeekableStream` iterator, allowing lookahead traversal.
3.  **Strict Top-Level Validation:** Before looking for actions, the `_parse_strict_top_level` method strictly validates the overall document structure. It enforces the exact sequence: `H1` Title -> Metadata `List` -> `H2` Rationale -> `CodeFence/BlockCode` -> (Optional `H2` Memos -> `CodeFence/BlockCode`) -> `H2` Action Plan.
4.  **Single-Pass Strict Dispatch Loop:** The parser iterates through the stream of top-level nodes in the `## Action Plan` section.
    *   **Action Detection:** When it encounters a Level 3 `Heading` matching a known `ActionType` (e.g., `### CREATE`), it dispatches control to the corresponding specific parser handler.
    *   **Strict Structural Validation:** The parser enforces a rigid, "fail-fast" structure. If it encounters any node between actions that is *not* a valid action heading (such as a `ThematicBreak` (`---`), stray text, or malformed blocks), it immediately triggers a structural error. It does not attempt to ignore or "auto-correct" invalid content.
5.  **Actionable AST Diff Feedback:** When a structural violation occurs, `_raise_structural_error` halts parsing and throws an `InvalidPlanError` containing a high-fidelity "AST Diff." This diff explicitly compares the expected document node blueprint against the actual AST nodes found, highlighting the exact mismatch and providing a hint regarding improperly nested code blocks.
6.  **Specific Parsers:** Each handler (e.g., `_parse_create_action`) consumes nodes from the stream to build the `ActionData` object. They enforce the internal grammar of the specific action and rely on `_parse_action_metadata` to uniformly extract key-value pairs from the metadata list.
6.  **POSIX Pre-Processing:** For `EXECUTE` actions, the parser uses an `_extract_posix_headers` helper to process the raw shell command string. It extracts `cd <path>` and `export KEY=value` directives from the *top* of the script (the "Header Block"), maps them to the action's `cwd` and `env` parameters, and strips them from the final command. It stops extraction upon encountering the first standard command, leaving subsequent directives intact. It supports a graceful fallback by merging legacy `cwd`/`env` metadata with the extracted header directives.

## 3. Dependencies

-   **`mistletoe`:** For parsing Markdown into an AST.

## 4. Error Handling

-   If the Markdown structure deviates from the specification (e.g., a missing `#` heading, a malformed action block), the parser will raise a `MarkdownPlanParsingError` with a descriptive message.

## 5. Implementation Notes (from Spike)

The technical spike (`spikes/plumbing/01_mistletoe_parser/`) confirmed the viability of using `mistletoe`. The key finding relates to the AST structure for extracting linked file paths from a metadata list:

-   **Correct Traversal Path:** A `Link` token is not a direct child of a `ListItem`. The correct path to traverse the AST is `ListItem -> Paragraph -> Link`. The parser implementation must account for this intermediate `Paragraph` token to reliably extract link targets.
