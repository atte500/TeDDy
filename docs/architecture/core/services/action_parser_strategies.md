# Component: Action Parser Strategies

## 1. Responsibility
The `action_parser_strategies` module implements the specific parsing logic for each supported TeDDy action (e.g., `CREATE`, `EDIT`, `EXECUTE`). It is utilized by the `MarkdownPlanParser` via a strategy pattern, allowing the main parser to remain compact and focused on the overall document structure.

## 2. Key Functions

### Action Parsers
Each function follows a consistent signature, taking a `_PeekableStream` and returning a populated `ActionData` object:
- `parse_create_action(stream)`
- `parse_read_action(stream)`
- `parse_edit_action(stream, valid_actions)`
- `parse_execute_action(stream)`
- `parse_research_action(stream, valid_actions)`
- `parse_chat_with_user_action(stream, valid_actions)`
- `parse_prune_action(stream)`
- `parse_invoke_action(stream, valid_actions)`
- `parse_return_action(stream, valid_actions)`

### Helper Functions
- `parse_action_metadata(...)`: A generalized utility for extracting `Description`, `File Path`, and other parameters from the bulleted list that follows an action heading. It handles both plain text and Markdown links.
- `extract_posix_headers(...)`: Processes `cd` and `export` directives from the top of an `EXECUTE` action's shell block.

## 3. Design Principles
- **Extensibility:** Adding a new action type primarily involves adding a new strategy function to this module and updating the `MarkdownPlanParser`'s dispatch map.
- **Fail-Fast Validation:** Strategies raise `InvalidPlanError` immediately upon encountering malformed action-specific structures, providing detailed feedback to the AI agent.
