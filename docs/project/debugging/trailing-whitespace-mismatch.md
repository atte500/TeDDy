# MRE: EditMatcher Fails on Trailing Whitespace

## 1. Failure Context
An `EDIT` action fails to find a match in `tests/suites/acceptance/test_console_reviewer.py`. The similarity score is 0.93, suggesting a near-miss. The diff indicates trailing whitespace on several lines in the target file that are absent in the `FIND` block.

## 2. Steps to Reproduce
1. Execute a plan containing an `EDIT` action for `tests/suites/acceptance/test_console_reviewer.py`.
2. Use a `FIND` block that matches the content but excludes any trailing spaces that might exist in the file.
3. Observe the `Validation Failed` report with similarity < 0.95.

## 3. Expected vs Actual
- **Expected:** The matcher should be indifferent to trailing whitespace (spaces/tabs) if the core content matches, or at least identify the match with 1.0 similarity if the only difference is trailing whitespace (similar to the Newline Indifference Bonus).
- **Actual:** Similarity score drops below the threshold, causing a validation failure.

## 4. Relevant Code
- `src/teddy_executor/core/services/validation_rules/edit_matcher.py`
- `src/teddy_executor/core/services/edit_simulator.py`

## 5. Investigation Log
### Current Leading Theory
The `EditMatcher` uses a "Line Ending Indifference Bonus": `window_str.rstrip("\r\n") == find_block.rstrip("\r\n")`. This only handles newline characters. If the target file has trailing spaces or tabs (e.g. from an IDE's auto-indent or poor linting), these remain in `window_str` while being absent in the AI-generated `find_block`.

### Verification (Spike)
- `spikes/debug/test_whitespace_indifference.py` confirms that `rstrip("\r\n")` leaves trailing spaces, causing `difflib` ratios < 1.0.
- Using a more aggressive `rstrip()` (stripping all trailing whitespace) results in a perfect 1.0 match for these cases.

## 6. Proposed Fix

| Strategy | Pros | Cons | Regression Risk |
| :--- | :--- | :--- | :--- |
| **1. Aggressive `rstrip()`** | Simple, idiomatic, covers all trailing whitespace. | None (trailing whitespace is non-semantic in Python/Markdown). | Low |
| **2. Targeted `rstrip(" \t\r\n")`** | Explicitly defines what characters are ignored. | More verbose. | Low |

### Primary Recommendation
**Strategy 3 (Line-by-line Normalization)** is recommended. Initial exploration of `rstrip()` showed it is insufficient for multi-line blocks where trailing whitespace exists on intermediate lines.

The normalization logic:
`"\n".join(line.rstrip() for line in s.splitlines())`

This approach correctly handles trailing spaces/tabs on every line of the block while preserving critical leading whitespace (indentation). It was validated in `spikes/debug/validate_fix.py`.

## 7. Root Cause Analysis
The `EditMatcher` implements a "Line Ending Indifference Bonus" to treat files with mismatched `\n` vs `\r\n` as perfect matches (1.0).

**Technical Flaw:**
The current implementation:
`if ratio < 1.0 and "".join(window).rstrip("\r\n") == find_block.rstrip("\r\n"): ratio = 1.0`

By passing `"\r\n"` to `rstrip()`, the method *only* strips those specific characters. If the target file contains trailing spaces or tabs (e.g., from an editor's auto-format), those characters remain in the `window` string. Since the AI-generated `FIND` block is typically "clean" (no trailing spaces), the equality check fails.

For a 10-line block, a single line with trailing spaces drops the `difflib` ratio to ~0.95. Two or more such lines drop it to ~0.93, which is below the default `0.95` threshold, resulting in a validation failure.

## 8. Implementation Notes
- **Fix Location:** `src/teddy_executor/core/services/validation_rules/edit_matcher.py`
- **Method:** `_refine_and_select_best`
- **Logic:** Replaced narrow `rstrip("\r\n")` check with a line-by-line normalization that ignores all trailing whitespace (spaces, tabs, newlines) on every line in the block.
- **Regression Tests:** Created `tests/suites/unit/core/services/test_edit_matcher_whitespace.py` covering mismatched intermediate line trailing spaces, indentation significance, and logic change detection.
- **Alignment:** Updated existing tests in `test_edit_simulator_fuzzy.py` and `test_validator_edit_resilience.py` to use logic changes for threshold verification, as trailing whitespace is no longer considered a "fuzzy" mismatch.

## 9. Architectural Remediation
- **Standardized Normalization:** The project should consider a centralized `WhitespaceNormalizer` utility to ensure consistent comparison logic across the parser, validator, and reporter.
- **Linting Encouragement:** The prevalence of trailing whitespace in target files suggests that adding a "lint-on-save" or "pre-commit" check to the repository would reduce the surface area for these types of mismatches.
