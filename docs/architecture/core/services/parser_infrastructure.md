# Component Design: Parser Infrastructure
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/parser_infrastructure.py`](/src/teddy_executor/core/services/parser_infrastructure.py)

## Purpose
A stateless module of low-level utilities shared by the plan parser: AST traversal, a peekable node stream, code-fence normalization, heading normalization, path normalization, and parameter coercion.

## Consumers
- [`MarkdownPlanParser`](./markdown_plan_parser.md): Uses the stream, the fence pre-processor, heading normalization, and the AST helpers.
- [`Action Parser Strategies`](./action_parser_strategies.md): Uses the stream wrapper and the parameter-coercion helpers.
- [`Parser Metadata`](./parser_metadata.md): Uses the path-normalization and node-traversal helpers.

## Dependencies
- `mistletoe` (external): Supplies the AST token types checked by the helpers; token imports are guarded so none runs at module load.

## Class Invariants
- `stateless_pure_functions`: Every helper is a pure function of its arguments.
- `lazy_token_imports`: `mistletoe` token classes are imported inside functions to keep CLI startup fast.
- `url_safe_path_normalization`: `normalize_path` converts backslashes to forward slashes and percent-decodes, but returns URLs intact.

## Inbound Ports
None — this module is an internal helper surface.

## Outbound Ports
None — the module declares no injected dependencies.

## Data Contracts
- **`_PeekableStream`**: A wrapper over an iterator exposing `has_next`, `peek`, and `next` for one-token lookahead.
- **Level constants (`H1_LEVEL`, `H2_LEVEL`, `H3_LEVEL`)**: Heading depth markers used across the parser.
- **`EXPECTED_KV_PARTS`**: The expected segment count for a key-value split.

## Operations

### `normalize_headings(content) -> str`
- **Preconditions:** None.
- **Postconditions:** Inserts the missing space after `#` on the first line only (for example `#Title` becomes `# Title`).

### `normalize_path(path) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns a POSIX-style, percent-decoded path; returns URLs unchanged.

### `normalize_link_target(target) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns project-relative targets without a leading slash, and preserves true absolute paths and external URLs.

### `get_child_text(node) -> str`
- **Preconditions:** `node` is a mistletoe token.
- **Postconditions:** Returns the concatenated text of the node and its descendants.

### `get_action_heading(node, valid_actions) -> Optional[Heading]`
- **Preconditions:** `valid_actions` is the set of known action names.
- **Postconditions:** Returns the node when it is a level-3 heading naming a known action; otherwise returns `None`.

### `consume_content_until_next_action(stream, valid_actions) -> list`
- **Preconditions:** None.
- **Postconditions:** Consumes nodes until the next action heading or a section boundary and returns the consumed nodes.

### `find_node_in_tree(node, node_type) -> Optional[Any]`
- **Preconditions:** None.
- **Postconditions:** Returns the first descendant of the requested type; otherwise returns `None`.

### `translate_setup_commands(setup_str, initial_cwd=None, initial_env=None) -> tuple`
- **Preconditions:** `setup_str` is a `&&`-chained command string.
- **Postconditions:** Returns the resolved `(cwd, env)` pair, honoring `cd` and `export` directives.

### `coerce_param(value, expected_type) -> Any`
- **Preconditions:** None.
- **Postconditions:** Returns the coerced value, or `None` when coercion fails.

### `coerce_action_params(params, type_map) -> dict`
- **Preconditions:** None.
- **Postconditions:** Coerces the listed keys in place and removes any key that cannot be coerced.

### `print_ast(token, indent=0) -> None`
- **Preconditions:** None.
- **Postconditions:** Prints an indented AST trace to stdout for debugging.

### Internal helpers
`_FencePreProcessor.process` strips trailing non-whitespace content on fence lines of six or more backticks or tildes, skipping any line whose trailing content holds a fence character. `_PeekableStream` provides the one-token lookahead used across the parser.
