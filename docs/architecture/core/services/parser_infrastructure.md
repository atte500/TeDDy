# Component: Parser Infrastructure

## 1. Responsibility
The `parser_infrastructure` module provides low-level utilities and helper classes used by the `MarkdownPlanParser` and its associated strategies. It encapsulates the mechanics of AST traversal and stream handling, keeping the high-level parsing logic clean and focused on business rules.

## 2. Key Components

### `_PeekableStream`
A wrapper around an iterator that allows the parser to "peek" at the next node in the Markdown AST without consuming it. This is essential for the single-pass, look-ahead parsing strategy.

### `_FencePreProcessor`
Ensures that Markdown code fences (e.g., ` ``` `) are handled consistently before the document is parsed into an AST. It serves as a hook for normalizing LLM-generated Markdown that might use variable fence lengths.

### AST Helpers
- `get_child_text(node)`: Recursively extracts all plain text content from a Markdown node and its children.
- `get_action_heading(node, valid_actions)`: Identifies if a node is a valid Level 3 Action Heading.
- `find_node_in_tree(node, node_type)`: Performs a depth-first search for a specific node type within an AST subtree.
- `consume_content_until_next_action(stream, valid_actions)`: Streams through nodes until a structural boundary (like the next action or a higher-level heading) is encountered.
- `extract_posix_headers(command_str, initial_cwd, initial_env)`: Parses and removes `cd` and `export` directives from the beginning of a shell script string.

### Path Normalization
- `normalize_path(path)`: Ensures all paths use POSIX-style forward slashes for internal consistency.
- `normalize_link_target(target)`: An OS-aware heuristic that distinguishes between project-relative paths (e.g., `[/docs/spec.md]`) and true system absolute paths (e.g., `/etc/passwd`).

## 3. Design Principles
- **Separation of Concerns:** Infrastructure mechanics are isolated from the plan's domain logic.
- **Statelessness:** Most helpers are pure functions that operate directly on AST nodes.
