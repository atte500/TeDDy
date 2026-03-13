# Service: `MarkdownPlanParser`

**Status:** Implemented
**Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose
The `MarkdownPlanParser` service is responsible for parsing a plan written in the proprietary Markdown format specified in the [New Plan Format Specification](../../specs/new-plan-format.md). It transforms the Markdown text into a valid `Plan` domain object that can be consumed by the `ExecutionOrchestrator`.

## 2. Core Responsibilities
- **AST Parsing:** Uses the `mistletoe` library to parse Markdown into an Abstract Syntax Tree (AST).
- **Structural Validation:** Enforces a strict, top-level document structure (H1 Title -> Metadata List -> Rationale -> Action Plan) using a single-pass traversal strategy. Any deviation triggers an `InvalidPlanError` with a rich structural diagnostic report (Status icons, indices, and surgical error messages).
- **Precise Error Propagation:** Action strategies are responsible for identifying structural failures within their own blocks and propagating the specific `offending_node` to ensure diagnostic reports pinpoint the exact location of the error.
- **Action Dispatching:** Iterates through the `## Action Plan` section and dispatches parsing control to specialized strategy functions based on the detected action type.
- **Path Normalization:** Performs centralized normalization of project-relative paths, ensuring cross-platform compatibility.
- **Error Reporting:** Generates high-fidelity error reports, including a full AST summary of the document's top-level nodes. This trace identifies node types and highlights multiple `offending_nodes` (deviations from schema) using status indicators (`[✓]`, `[✗]`, `[ ]`) and descriptive error messages (`(Error: ...)`) to provide precise, actionable feedback.
- **Pre-processing:** Employs a `FencePreProcessor` to normalize code fence lengths and ensure correct AST generation for nested code blocks.

## 3. Supported Actions
The parser supports the following actions, each with its own parsing strategy:
- `CREATE`: Extracts file path and content.
- `EDIT`: Extracts file path and sequential `FIND`/`REPLACE` pairs.
- `READ`, `PRUNE`: Extracts resource path or URL.
- `EXECUTE`: Extracts the raw command block and metadata (Description, Expected Outcome, Allow Failure, Background, Timeout). Chaining and directives are preserved as-is in the command string for execution by the shell.
- `RESEARCH`: Extracts multiple web search queries.
- `PROMPT`: Extracts the markdown message to the user.
- `INVOKE`: Extracts the target agent, message, and optional handoff resources.
- `RETURN`: Extracts the completion message and optional handoff resources.

## 4. Modular Architecture
To maintain focus and adhere to file complexity limits, the parser delegates to specialized helper modules:
- **[Parser Infrastructure](./parser_infrastructure.md):** Low-level AST traversal utilities, stream handling (`_PeekableStream`), and high-fidelity AST structural reporting logic.
- **[Parser Metadata](./parser_metadata.md):** Logic for parsing action metadata lists and message content.
- **[Action Parser Strategies](./action_parser_strategies.md):** The specific grammar and dispatch logic for individual action types.

## 5. Implementation Notes
- **AST Traversal:** A key finding from the initial implementation spike is that `Link` tokens in a metadata list are not direct children of a `ListItem`; the traversal must account for an intermediate `Paragraph` token (`ListItem -> Paragraph -> Link`).
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
