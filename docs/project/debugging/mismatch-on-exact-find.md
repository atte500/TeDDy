# MRE: Fuzzy Matcher Returns Incorrect Window Size

## 1. Failure Context
The `EDIT` action validation fails to find an exact match for a block that exists in the file. The "Closest Match" reported in the validation error shows an extra line compared to the `FIND` block, resulting in a similarity score (0.94) below the threshold (0.95).

## 2. Steps to Reproduce
1. Use the content of `tests/suites/acceptance/test_context_aware_editing.py` provided in the report.
2. Attempt an `EDIT` with a `FIND` block containing the last 5 lines of the `test_context_aware_editing_modifies_create_action` function.
3. Observe the validation failure.

## 3. Expected vs Actual
- **Expected:** Exact match (Similarity 1.00).
- **Actual:** Similarity 0.94, closest match includes an extra line.

## 4. Relevant Code
- `src/teddy_executor/core/services/validation_rules/edit_matcher.py` (Likely location of the matching logic)
- `src/teddy_executor/core/services/edit_simulator.py`

## 5. Investigation Log
### Current Leading Theory
The matcher uses a fixed-size window based on `len(find_block.splitlines())`. However, the plan parser explicitly `rstrip("\n")` the `FIND` block. This removes the final newline character. If the `FIND` block is matched against a section of a file that is NOT at the absolute end of the file, the last line in the file will have a `\n` while the last line in the `find_block` will not. This character mismatch on the last line prevents a 1.00 similarity score.

Additionally, if the user intends to match a block that ends with an empty line, the stripping behavior might cause the matcher to select a window that is one line shorter than intended if the empty line's newline was the only thing distinguishing it.

## 6. Proposed Fix
Implemented a **"Line Ending Indifference Bonus"** in the `EditMatcher`. This logic explicitly checks if two strings that are currently scored below 1.0 are identical when trailing newlines (`\n` or `\r\n`) are removed. If they are, the match is upgraded to a perfect `1.0`.

## 7. Root Cause Analysis
The root cause was a fundamental character-level discrepancy between the `EDIT` action parser and the `EditMatcher`'s windowing logic:

1.  **Parser Stripping:** The Markdown parser (via `mistletoe`) and our `EDIT` action logic consistently `rstrip("\n")` the content of `FIND` blocks to handle Markdown's fenced code block trailing newline behavior. This ensures that the last line of a block never includes a trailing newline in the domain model.
2.  **Fixed-Window Matcher:** The `EditMatcher` selects a "window" of text from the target file based on the line count of the `FIND` block.
3.  **The Mismatch:** If the intended match in the target file is not at the very end of the file, its last line *always* contains a newline character.
4.  **Similarity Degradation:** When `difflib.SequenceMatcher` compares the stripped `find_block` against the unstripped `window`, it identifies a character mismatch on the very last byte. For short blocks (e.g., 6-10 lines), this single-character discrepancy is enough to drop the similarity ratio from `1.00` to `0.94`, which is below the default `0.95` threshold.

## 8. Implementation Notes
- **Precision Bonus:** The `EditMatcher._evaluate_candidates` function now includes a check: `if score < 1.0 and window_str.rstrip("\r\n") == find_block.rstrip("\r\n"): score = 1.0`.
- **Platform Agnostic:** The use of `rstrip("\r\n")` ensures that both LF and CRLF line endings are handled correctly without affecting internal string similarity.
- **Test Alignment:** Multiple tests in the suite were updated to use character-level changes (e.g., changing 'world' to 'worLd') for fuzzy testing, as newline mismatches are no longer treated as "fuzzy" by the matcher.

## 9. Architectural Remediation
- **Standardized Line Endings:** While the "Indifference Bonus" solves the symptoms, the project should eventually consider standardizing on a "Newline-Rich" or "Newline-Poor" internal representation for all file content and plan data to eliminate this class of errors entirely.
- **Matcher Transparency:** The current fix ensures that a `1.0` match is reported, which correctly suppresses the fuzzy match diff in the report, improving UX.
