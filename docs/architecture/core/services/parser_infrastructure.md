# Component: Parser Infrastructure

## Purpose / Responsibility

Provides low-level AST traversal utilities, stream management (_PeekableStream), and path normalization used by the MarkdownPlanParser during plan parsing. Also houses the _FencePreProcessor which normalizes raw plan Markdown before AST parsing.

## Implementation Details / Logic

### _FencePreProcessor
The `_FencePreProcessor` class is responsible for normalizing raw Markdown plan output before AST parsing. It currently handles two tasks:

1. **Code Fence Normalization:** Adjusts fence lengths to ensure valid nested code blocks.
2. **Closing Fence Trailing Text Stripping:** Scans each line of the plan string. If a line (after optional leading whitespace) consists of 6 or more consecutive backticks (`` ` ``) or tildes (`~`) followed by non-whitespace content, the trailing text is stripped. This prevents LLM artifacts like `~~~~~~ trailing text` from contaminating code block content.

#### Implementation Details (Trailing Text Stripping)

The stripping logic uses a single regex pattern and a guard condition:

- **Regex:** `"^(\s*)(\~{6,}|\`{6,})(.*)$"` — Matches optional leading whitespace (group 1), then a pure sequence of 6+ tildes OR 6+ backticks (group 2), then any trailing content (group 3).
- **Mixed-Fence Guard:** Before stripping, the implementation checks that group 3 does NOT contain any backtick or tilde characters. This prevents corrupting lines like `~~~~~~\` trailing` where fence characters appear in the trailing content (safe to keep such lines unchanged).
- **Sub-Threshold Protection:** Lines where the fence character sequence is fewer than 6 characters (e.g., `~~~~`, ``````) are never modified.

**Edge Cases Proven via Standalone Prototype:**
  - `"~~~~~~ trailing text"` → `"~~~~~~"` (standard case)
  - `"`````` trailing text"` → `"``````"` (backtick variant)
  - `"~~~~"` → unchanged (below threshold, 4 tildes)
  - `"~~~~~~python"` → `"~~~~~~"` (adjacent trailing text, no space)
  - `"    ~~~~~~ trailing"` → `"    ~~~~~~"` (indentation preserved)
  - `"~~~~~~"` → unchanged (fence only, no trailing text)
  - `"~~~~~~   "` → unchanged (fence with trailing whitespace only)
  - `"~~~~~~~~ text"` → `"~~~~~~~~"` (8-tilde fence, works for any length ≥6)
  - `"~~~~~~\` trailing"` → unchanged (mixed fence characters in trailing content)
  - `"Some text ~~~~~~ trailing"` → unchanged (fence chars mid-line, not at start)

### _PeekableStream
A wrapper around an iterator that provides one-token lookahead (`peek()`) and consumption (`next()`). Used by the parser for single-pass AST traversal.

### Tail-end Resilience in _parse_actions
Modified in `markdown_plan_parser.py` to silently consume trailing `BlockCode` and `CodeFence` nodes after the last action. This is consistent with the between-action skip logic implemented in Slice 02-06.

## 1. Responsibility
The `parser_infrastructure` module provides low-level utilities and helper classes used by the `MarkdownPlanParser` and its associated strategies. It encapsulates the mechanics of AST traversal and stream handling, keeping the high-level parsing logic clean and focused on business rules.

## 2. Key Components

### `_PeekableStream`
A wrapper around an iterator that allows the parser to "peek" at the next node in the Markdown AST without consuming it. This is essential for the single-pass, look-ahead parsing strategy.

### `_FencePreProcessor`
Ensures that Markdown code fences (e.g., ` ``` `) are handled consistently before the document is parsed into an AST. It serves as a hook for normalizing LLM-generated Markdown that might use variable fence lengths.

### Constants
*(No public constants are currently exported; constants are managed internally.)*

### AST Helpers
- `get_child_text(node)`: Recursively extracts all plain text content from a Markdown node and its children.
- `get_action_heading(node, valid_actions)`: Identifies if a node is a valid Level 3 Action Heading.
- `find_node_in_tree(node, node_type)`: Performs a depth-first search for a specific node type within an AST subtree.
- `consume_content_until_next_action(stream, valid_actions)`: Streams through nodes until a structural boundary (like the next action or a higher-level heading) is encountered.
- `extract_posix_headers(command_str, initial_cwd, initial_env)`: Parses and removes `cd` and `export` directives from the beginning of a shell script string.
- `format_node_name(node)`: Formats the AST node type with metadata (e.g., heading level or code fence backtick count) for reporting.
- `format_structural_mismatch_msg(doc, expected, mismatch_idx, offending_nodes)`: Constructs a rich diagnostic report for structural failures.
    - **Status Icons**: Nodes are marked as `[✓]` (valid), `[✗]` (failing), or `[ ]` (unvalidated context).
    - **Indices**: Every node is indexed for clear reference.
    - **Error Context**: Failing nodes include parenthetical error messages detailing the expectation.
    - **Cutoff Logic**: Structural parsing becomes unreliable after a failure; all nodes following the first detected failure are marked as `[ ]` to avoid false positives.

### Path Normalization
- `normalize_path(path)`: Ensures all paths use POSIX-style forward slashes for internal consistency.
- `normalize_link_target(target)`: An OS-aware heuristic that distinguishes between project-relative paths (e.g., `[/docs/spec.md]`) and true system absolute paths (e.g., `/etc/passwd`).

## 3. Design Principles
- **Separation of Concerns:** Infrastructure mechanics are isolated from the plan's domain logic.
- **Statelessness:** Most helpers are pure functions that operate directly on AST nodes.
