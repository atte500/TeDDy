# Component Design: EditSimulator
**Status:** Planned
**Introduced in:** [09-cli-polish-and-ux-improvements](/docs/project/slices/09-cli-polish-and-ux-improvements.md)

## 1. Purpose / Responsibility
The `EditSimulator` is a pure domain service responsible for applying a sequence of `FIND`/`REPLACE` operations to a string in memory. It encapsulates the logic for verbatim replacement, match counting, and handling edge cases (like trailing newlines) without any I/O dependencies.

## 2. Ports
- **Type:** Core Service
- **Implements:** `IEditSimulator` (Inbound Port)

## 3. Implementation Details / Logic
The simulator iterates through the provided list of edits and applies them sequentially. It reuses the logic previously found in `LocalFileSystemAdapter`:
1.  Verify the `find` string exists exactly once in the current content.
2.  If it doesn't, raise a domain-specific exception (`SearchTextNotFoundError` or `MultipleMatchesFoundError`).
3.  Apply the replacement.
4.  Handle special "empty replace" logic to clean up trailing newlines if the `find` block included them.

## 4. Data Contracts / Methods

### `simulate(content: str, edits: list[dict[str, str]]) -> str`
- **Preconditions:** `content` is a string; `edits` is a list of dictionaries with `find` and `replace` keys.
- **Postconditions:** Returns the new string after all edits are applied.
- **Exception/Error States:**
    - `SearchTextNotFoundError`: Raised if a `find` block is not found.
    - `MultipleMatchesFoundError`: Raised if a `find` block is ambiguous.
