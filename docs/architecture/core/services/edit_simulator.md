# Component Design: EditSimulator
**Status:** Implemented
**Introduced in:** [09-cli-polish-and-ux-improvements](/docs/project/slices/09-cli-polish-and-ux-improvements.md)

## 1. Purpose / Responsibility
The `EditSimulator` is a pure domain service responsible for applying a sequence of `FIND`/`REPLACE` operations to a string in memory. It encapsulates the logic for fuzzy matching, resilient replacement, and handling edge cases (like trailing newlines) without any I/O dependencies.

## 2. Ports
- **Type:** Core Service
- **Implements:** `IEditSimulator` (Inbound Port)

## 3. Implementation Details / Logic
The simulator iterates through the provided list of edits and applies them sequentially. It leverages the `edit_matcher` for resilient target location:
1.  Identify matching candidate(s) using a unified matching engine (`edit_matcher.py`) with a `similarity_threshold`.
2.  **Ambiguity Detection:** If `replace_all` is `false` and multiple candidates share the same highest score, raise `MultipleMatchesFoundError`.
3.  **Replacement Logic:**
    - If `replace_all` is `true`, replace *every* occurrence meeting the threshold.
    - If `replace_all` is `false`, replace only the single best match.
4.  Handle special "empty replace" logic to clean up trailing newlines if the identified match block included them.

## 4. Data Contracts / Methods

### `simulate_edits(content: str, edits: list[dict[str, str]], threshold: float = 0.95, replace_all: bool = False) -> tuple[str, list[float]]`
- **Preconditions:** `content` is a string; `edits` is a list of dictionaries with `find` and `replace` keys.
- **Postconditions:** Returns a tuple containing the new string and a list of similarity scores for applied edits.
- **Preconditions:** `content` is a string; `edits` is a list of dictionaries with `find` and `replace` keys.
- **Postconditions:** Returns the new string after all edits are applied.
- **Exception/Error States:**
    - `SearchTextNotFoundError`: Raised if a `find` block is not found within threshold.
    - `MultipleMatchesFoundError`: Raised if a `find` block is ambiguous or a tie is detected.
