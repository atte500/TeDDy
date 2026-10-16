# Component Design: MarkdownPlanParser
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/markdown_plan_parser.py`](/src/teddy_executor/core/services/markdown_plan_parser.py)

## Purpose
Implements the `IPlanParser` inbound port. It transforms a Markdown plan string into a valid `Plan` domain object through a strict, single-pass AST traversal that produces high-fidelity structural diagnostics on failure.

## Consumers
- [`ExecutionOrchestrator`](./execution_orchestrator.md): Parses raw plan content before executing an approved plan, consuming the parser only through the `IPlanParser` port.
- [Composition Root](/src/teddy_executor/container.py): Instantiates the parser and injects it as `IPlanParser`.

## Dependencies
- [`parser_infrastructure`](./parser_infrastructure.md): Supplies `_PeekableStream`, `_FencePreProcessor`, the heading normalizer, the AST helpers, and the structural report formatter.
- [`parser_metadata`](./parser_metadata.md): Supplies `parse_plan_metadata` for the top-level metadata list.
- [`action_parser_strategies`](./action_parser_strategies.md): Supplies the CREATE and READ strategies reached through the dispatch map.
- [`action_parser_complex`](/src/teddy_executor/core/services/action_parser_complex.py): Supplies the EDIT, EXECUTE, RESEARCH, and MESSAGE strategies.
- `mistletoe` (external): Supplies the AST `Document`; imported lazily inside `parse` to keep CLI startup fast.

## Class Invariants
- `partial_dispatch_map`: `_dispatch_map` routes CREATE, READ, EDIT, EXECUTE, and RESEARCH; MESSAGE is deliberately absent and is special-cased to a mutual-exclusivity error.
- `strict_top_level_schema`: The document must present an H1 title, a metadata list, an H2 `Rationale`, then an H2 `Action Plan` or `Message`; any deviation raises `InvalidPlanError`.
- `mutual_exclusivity`: A document cannot carry both `## Action Plan` and `## Message`.
- `constructor_holds_no_plan_state`: `parse` keeps no plan state on the instance; the constructor only builds the pre-processor, the valid-action set, and the dispatch map.

## Inbound Ports
- **`IPlanParser`**: Exposes the single `parse(plan_content, plan_path=None)` operation.

## Outbound Ports
None — the parser depends only on internal parser helpers and one lazily imported external library.

## Data Contracts
- **`Plan`** (`teddy_executor.core.domain.models`): The parsed domain object returned by `parse`.
- **`ActionData`** (`teddy_executor.core.domain.models`): The per-action record produced by the dispatch strategies.
- **`InvalidPlanError`** (`teddy_executor.core.ports.inbound.plan_parser`): Carries `offending_nodes` for the structural diagnostic report.
- **`ActionType`** (`teddy_executor.core.domain.models`): Supplies the valid-action set used for heading matching.

## Operations

### `MarkdownPlanParser()`
- **Preconditions:** None.
- **Postconditions:** Builds `_preprocessor`, the `_valid_actions` set from `ActionType`, and the `_dispatch_map`.

### `parse(plan_content, plan_path=None) -> Plan`
- **Preconditions:** `plan_content` is a non-empty string.
- **Postconditions:** Returns a `Plan`. The method trims trailing whitespace, strips any preamble before the first heading marker at line start, normalizes the H1 line, runs the fence pre-processor, builds the AST, validates the top-level schema, enforces mutual exclusivity, then parses the `Message` or `Action Plan` section. A session plan path (`.../.teddy/sessions/...`) sets `is_session` and writes the normalized content back to disk when it differs.
- **Exceptions:** `InvalidPlanError` when the content is empty or violates the schema, mutual exclusivity, or action grammar. The raised error carries a rendered AST diagnostic.

### Internal helpers
`_parse_strict_top_level` consumes the title, the metadata list, the rationale, and the section heading. `_validate_mutual_exclusivity` scans the H2 headings. `_parse_section_content` routes to the message or action-plan parser. `_parse_actions` dispatches each action heading and skips inter-action code blocks and thematic breaks. `_raise_structural_error`, `_format_structural_mismatch_msg`, and `_consume_mandatory_node` build the diagnostics.
