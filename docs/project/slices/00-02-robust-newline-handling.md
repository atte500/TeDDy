# Slice: Robust Newline Handling

- **Status:** Planned
- **Milestone:** None (Fast-Track)
- **Specs:** [docs/project/debugging/mismatch-on-exact-find.md](/docs/project/debugging/mismatch-on-exact-find.md)

## 1. Business Goal
Ensure that surgical `EDIT` operations are resilient to the trailing newline stripping performed by Markdown parsers, while guaranteeing that the file's original line endings (LF or CRLF) are preserved to avoid "Git Noise."

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Exact Match with Missing Newline (Small Block)
**Given** a file `test.py` containing `print('hello')\n`
**And** an `EDIT` plan with `FIND: "print('hello')"` (no newline)
**When** I execute the plan
**Then** the matcher should return a `1.0` score
**And** the replacement should be applied successfully.

#### Deliverables
- [✓] Updated `EditMatcher` test suite to include "Indifference Bonus" cases for exact content with mismatched endings.

### Scenario 2: Exact Match with Missing Newline (Large Block)
**Given** a file with 25 lines of code ending in `\r\n`
**And** a `FIND` block containing the exact 25 lines but without the final `\r\n`
**When** I execute the plan
**Then** the matcher should return a `1.0` score (overriding the list-of-lines ratio).

#### Deliverables
- [✓] Refactored `EditMatcher._evaluate_candidates` to apply the "Indifference Bonus" to the refinement phase of large blocks.

## Implementation Notes

### Indifference Bonus (Scenarios 1 & 2)
- **Unified Logic:** The "Indifference Bonus" logic was refactored from `_evaluate_candidates` (small blocks) into `_refine_and_select_best`. This ensures that any candidate that is identical to the `FIND` block (ignoring trailing `\r\n`) receives a perfect `1.0` score.
- **Large Block Resilience:** For blocks exceeding `LARGE_BLOCK_LINE_LIMIT`, the bonus now overrides the line-list based ratio if the raw string content matches (minus newlines).
- **Test Coverage:** Added `tests/suites/unit/core/services/test_edit_matcher_indifference.py` covering small blocks, large blocks, and CRLF indifference.

### Scenario 3: Line Ending Preservation (Zero Git Noise)
**Given** a file with CRLF (`\r\n`) line endings
**And** an `EDIT` plan that matches a block
**When** the replacement is applied
**Then** the newly inserted lines MUST use `\r\n`
**And** the rest of the file MUST NOT be converted to LF.

#### Deliverables
- [ ] Updated `EditSimulator` to detect the line ending of the `best_match` and append the correct terminator (`\n` or `\r\n`) to the replacement text.

## 3. Architectural Changes

### `EditMatcher` (src/teddy_executor/core/services/validation_rules/edit_matcher.py)
- **Normalization:** Ensure that the `1.0` bonus logic is applied consistently regardless of block size.
- **Logic:** `if score < 1.0 and window_str.rstrip("\r\n") == find_block.rstrip("\r\n"): score = 1.0`.

### `EditSimulator` (src/teddy_executor/core/services/edit_simulator.py)
- **Dynamic Injection:** Replace the hardcoded `final_replace += "\n"` with logic that inspects the `best_match` suffix.
- **Constraint:** If the `best_match` ended in `\r\n`, the replacement must end in `\r\n`.

### Test Harness Triad
- **Setup:** Create a test utility to generate files with mixed or specific line endings for integration tests.
- **Observer:** The `FileSystemObserver` already reads raw content; ensure assertions check for `\r\n` explicitly in "Zero Git Noise" tests.
