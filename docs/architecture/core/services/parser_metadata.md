# Component: Parser Metadata

## 1. Responsibility
The `parser_metadata` module provides high-level parsing functions for extracting structured data from Markdown lists and text blocks within a TeDDy plan. It encapsulates the rules for handling metadata fields (like `Description`, `File Path`, and `env`) and cross-action message blocks.

## 2. Key Functions

### `parse_action_metadata(...)`
A generalized utility for extracting parameters from the bulleted list that follows an action heading.
- **Link Handling:** Automatically resolves root-relative Markdown links (e.g., `[path](/path)`) into normalized paths using the `ParserInfrastructure`.
- **Text Handling:** Extracts key-value pairs from plain text bullet items.

### `parse_env_from_metadata(metadata_list)`
Specifically parses a nested environment variable list (e.g., an `env:` item containing sub-items like `KEY: VALUE`).

### `parse_message_and_optional_resources(stream, valid_actions)`
A complex parser that consumes the stream after an action's metadata list to extract:
1.  An optional list of **Handoff Resources**.
2.  All subsequent Markdown content (paragraphs, blocks) until the next action heading or structural boundary is reached.

## 3. Design Principles
- **DRY (Don't Repeat Yourself):** Centralizes metadata logic used by multiple action strategies (`INVOKE`, `RETURN`, `EXECUTE`, etc.).
- **Robustness:** Handles both well-formed links and plain text fallbacks for resource paths.
