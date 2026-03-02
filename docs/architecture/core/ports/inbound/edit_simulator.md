# Inbound Port: `IEditSimulator`

**Status:** Implemented

## 1. Purpose

The `IEditSimulator` defines the port for a service that can simulate the result of applying one or more `EDIT` operations (FIND/REPLACE pairs) to a string in memory without modifying any files. This is used for both pre-execution validation and generating unified diff previews for the user.

## 2. Port Contract

### `simulate_edits(content: str, edits: list[dict[str, str]]) -> str`
Applies a sequence of edits to the provided content and returns the modified string.

- **Args:**
    - `content`: The original source string.
    - `edits`: A list of dictionaries, each containing `find` and `replace` keys.
- **Returns:** The string after all edits have been applied in sequence.
- **Raises:**
    - `SearchTextNotFoundError`: If a `find` block is not found in the content.
    - `MultipleMatchesFoundError`: If a `find` block is ambiguous.
