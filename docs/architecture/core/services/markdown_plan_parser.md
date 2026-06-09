# Service: `MarkdownPlanParser`

**Status:** Implemented
**Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose
The `MarkdownPlanParser` service is responsible for parsing a plan written in the proprietary Markdown format specified in the [New Plan Format Specification](../../specs/new-plan-format.md). It transforms the Markdown text into a valid `Plan` domain object that can be consumed by the `ExecutionOrchestrator`.

## 2. Core Responsibilities
- **AST Parsing:** Uses the `mistletoe` library to parse Markdown into an Abstract Syntax Tree (AST).
- **Structural Validation:** Enforces a strict, top-level document structure (H1 Title -> Metadata List -> Rationale -> Action Plan OR Message) using a single-pass traversal strategy. It enforces mutual exclusivity between the `## Action Plan` and `## Message` sections. Any deviation triggers an `InvalidPlanError` with a rich structural diagnostic report (Status icons, indices, and surgical error messages).
- **Terminal Message Section:** If a `## Message` heading is detected, the parser treats it as a terminal section, capturing all remaining Markdown content until the end of the file as the message body.
- **Precise Error Propagation:** Action strategies are responsible for identifying structural failures within their own blocks and propagating the specific `offending_node` to ensure diagnostic reports pinpoint the exact location of the error.
- **Action Dispatching:** Iterates through the `## Action Plan` section and dispatches parsing control to specialized strategy functions based on the detected action type.
- **Path Normalization:** Performs centralized normalization of project-relative paths, ensuring cross-platform compatibility.
- **Error Reporting:** Generates high-fidelity error reports, including a full AST summary of the document's top-level nodes. This trace identifies node types and highlights multiple `offending_nodes` (deviations from schema) using status indicators (`[✓]`, `[✗]`, `[ ]`) and descriptive error messages (`(Error: ...)`) to provide precise, actionable feedback.
- **Preamble Stripping:** Before AST construction, the parser strips any content before the first `# ` heading (H1) using a regex-based search (`(?:^|\n)# (?!#)`). This prevents preamble text from causing structural validation errors and ensures it does not appear in the parsed plan's `raw_content`.
- **Pre-processing:** Employs a `FencePreProcessor` to normalize code fence lengths and ensure correct AST generation for nested code blocks.

## 3. Supported Actions
The parser supports the following actions, each with its own parsing strategy:
- `MESSAGE`: Extracts the raw Markdown content from the `## Message` section.
- `CREATE`: Extracts file path and content.
- `EDIT`: Extracts file path, optional `Similarity Threshold`, and sequential `FIND`/`REPLACE` pairs.- `READ`, `PRUNE`: Extracts resource path or URL.
- `EXECUTE`: Extracts the raw command block and metadata (Description, Expected Outcome, Allow Failure, Background, Timeout). Chaining and directives are preserved as-is in the command string for execution by the shell.
- `RESEARCH`: Extracts multiple web search queries. It splits the content of each code block by newlines, treating each non-empty, stripped line as an individual query.
- `PROMPT`: Extracts the markdown message to the user.
- `INVOKE`: Extracts the target agent, message, and optional handoff resources.
- `RETURN`: Extracts the completion message and optional handoff resources.

*Note on Terminal Actions:* If a terminal action (`PROMPT`, `INVOKE`, `RETURN`) is parsed as part of a multi-action plan, the parser explicitly initializes its `selected` state to `False`. This allows the TUI to present it as deselected by default while causing headless executions to safely skip it.

## 4. Modular Architecture
To maintain focus and adhere to file complexity limits, the parser delegates to specialized helper modules:
- **[Parser Infrastructure](./parser_infrastructure.md):** Low-level AST traversal utilities, stream handling (`_PeekableStream`), and high-fidelity AST structural reporting logic.
- **[Parser Metadata](./parser_metadata.md):** Logic for parsing action metadata lists and message content.
- **[Action Parser Strategies](./action_parser_strategies.md):** The specific grammar and dispatch logic for individual action types.

## 5. Implementation Notes
- **AST Traversal:** A key finding from the initial implementation spike is that `Link` tokens in a metadata list are not direct children of a `ListItem`; the traversal must account for an intermediate `Paragraph` token (`ListItem -> Paragraph -> Link`).
- **Mutual Exclusivity Extraction (Slice 02-16):** The inline mutual exclusivity check in `parse` was extracted into a dedicated `_validate_mutual_exclusivity(self, doc)` method to reduce cyclomatic complexity. The method scans `doc.children` for H2 headings and raises `InvalidPlanError` if both "Action Plan" and "Message" are present.
- **Section Routing Extraction (Slice 02-16):** The inline section routing logic (branching on "Message" vs "Action Plan") was extracted into a dedicated `_parse_section_content(self, stream, clean_content, section_heading, doc)` method. This further reduces the cyclomatic complexity of `parse` and centralizes the content-routing decision.
- **Final Complexity Reduction (Slice 02-16):** After both extractions, the `parse` method's cyclomatic complexity dropped from 10 to ~5-6, well below the C901 threshold of 9. The `parse` method now consists of a linear sequence of calls to private helper methods.
- **Fence Pre-Processor (`_FencePreProcessor`):** The parser employs a pre-processing step (`parser_infrastructure._FencePreProcessor`) to normalize code fences before AST parsing. It strips trailing non-whitespace content on fence lines with 6+ consecutive backticks or tildes, preventing LLM artifacts like `~~~~~~ trailing text` from contaminating code block content. A mixed-fence guard prevents corruption of lines where fence characters appear in trailing content (e.g., `~~~~~~\` trailing`).
- **Trailing Code Block Resilience:** The `_parse_actions` method silently consumes trailing `BlockCode` and `CodeFence` nodes after the last action (via the existing between-action skip logic). `Paragraph` nodes at the tail-end still raise validation errors, preserving strict parsing for non-code-block content.
- **Schema Validation Complexity:** To adhere to cyclomatic complexity limits (Ruff C901), the top-level document schema validation is extracted into a dedicated `_validate_top_level_schema` method. This method scans the document for multiple structural deviations before data extraction begins.
-   **Defensive Type Handling for `mistletoe`:** The `mistletoe` Markdown parsing library exhibits a discrepancy between its runtime behavior and its static type hints. Specifically, attributes like `Token.children` are typed as a nullable `Iterable` but are consistently `list` instances at runtime.
    -   **Required Pattern:** To satisfy `mypy` and prevent runtime errors, any access to these attributes MUST be defensively converted to a concrete, non-nullable list first. Example: `children_list = list(token.children) if token.children else []`. This pattern ensures type safety and makes the code resilient to the library's loose type definitions.
-   **Single-Pass AST Parsing:** To ensure robustness against Markdown quirks (like `ThematicBreak` separators) and to simplify the parsing logic, the `MarkdownPlanParser` MUST use a "Single-Pass" strategy. It iterates through the AST nodes as a stream, dispatching to specific action parsers when an Action Heading is encountered and safely ignoring all interstitial content. This replaces the fragile "whitelist validation" approach.
-   **Cross-Platform Path Normalization:** To distinguish project-relative paths (e.g., `[/docs/spec.md]`) from true absolute paths, the `MarkdownPlanParser` uses an OS-aware heuristic.
    -   **Rule:** A path is considered a "true" absolute path only if it starts with a common system directory on POSIX (e.g., `/tmp`, `/etc`) or a drive letter on Windows. Other paths starting with `/` are treated as project-relative.
    -   **Rationale:** This allows the parser to normalize project-relative paths (by stripping the leading slash) while preserving true absolute paths to be rejected by the `PlanValidator`, ensuring consistent security and behavior across platforms.
-   **Strict Parser Validation:** The `MarkdownPlanParser` must enforce a strict structure within a plan's `## Action Plan` section.
    -   **Rule:** Any content found between valid action blocks (e.g., a `ThematicBreak` (`---`) or stray paragraphs) must be treated as a validation error. The parser should not attempt to ignore or "auto-correct" malformed plan structures.
    -   **Rationale:** This decision was the result of a pivot from an initial "robustness-first" approach. A strict, fail-fast parser is simpler, more predictable, and forces the upstream AI agent to produce well-formed plans, which is a core principle of the TeDDy workflow.
-   **Code Block Visibility in Diagnostics:** To facilitate debugging of nesting errors, `CodeFence` nodes in the AST trace include the number of backticks used in their delimiters (e.g., `CodeFence (5 backticks)`).
- **Lazy Loading for Performance:** To ensure the CLI remains responsive (initializing in under 500ms), heavy third-party libraries like `mistletoe` MUST be imported lazily within the methods where they are used (e.g., `parse`). Type hints for these libraries MUST use `TYPE_CHECKING` and forward references or `from __future__ import annotations` to prevent runtime `NameError`s.

### Tail-end Resilience in `_parse_actions`
Modified to silently consume trailing `BlockCode` and `CodeFence` nodes after the last action in the action plan section. This is consistent with the between-action skip logic implemented in Slice 02-06 and uses the same approach: iterating the stream after the main action-consuming loop and discarding any remaining `BlockCode` or `CodeFence` nodes. `Paragraph` nodes at the tail-end are NOT ignored and will still raise a validation error.

**Implementation Pattern (prototype-proven):**
```python
# Tail-end resilience: silently consume trailing code blocks
from mistletoe.block_token import BlockCode, CodeFence
while stream.has_next() and isinstance(stream.peek(), (BlockCode, CodeFence)):
    stream.next()
```

This loop must be placed in `_parse_actions` after the main `while stream.has_next()` loop that consumes action blocks and before the `return actions` statement. It is intentionally scoped to only skip `BlockCode` and `CodeFence` nodes — any other node type (notably `Paragraph`) at the tail end will still raise a validation error, preserving strict parsing for non-code-block content.
