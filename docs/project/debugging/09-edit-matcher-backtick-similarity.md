# Bug: Edit Matcher Heuristic Cascade Fails for Files ≥100 Lines
- **Status:** Resolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A (thin fix, no slice needed)
- **Specs:** N/A

## Symptoms
- **Expected:** When validating an `EDIT` action where the `FIND` block differs from the actual file content only by minor formatting (e.g., missing backticks around a word like `` `EDIT` `` vs `EDIT`), the matcher should return a score > 0.0 and include a "Closest Match Diff" in the validation error message.
- **Actual:** The matcher returns `score=0.00` with no "Closest Match Diff" block. The validation error says "Similarity Score: 0.00" with only the "Hint" message. This is specifically broken in session mode where the target file has ≥100 lines.
- **Minimal Reproduction:**
  1. Create a file with ≥100 lines containing the line: `- [ ] **Logic** - Implement mid-execution \`EDIT\` consistency: hash tracking after each successful edit and verification against external modifications.`
  2. Attempt to `EDIT` it with a `FIND` block that omits the backticks around `EDIT`.
  3. Validation reports score 0.00, no "Closest Match Diff" generated.

## Context & Scope

### Regressing Delta
This is not a regression from a single code change — it is a design flaw that has existed since the heuristic cascade was introduced. The heuristic tiers in `edit_matcher_heuristics.py` have two guard conditions that, in combination, silently fail for this class of input:
- `_find_starts_by_fuzzy_cascade` uses strict greater-than (`>`) instead of `>=` for comparing against threshold, disabling Tier 2 for any threshold ≥ 0.99.
- `SMALL_FILE_LINE_LIMIT = 100` disables Tier 4 (exhaustive search) for files with 100+ lines.

### Environmental Triggers
- File must have ≥100 lines (otherwise Tier 4 catches it).
- The difference between FIND and file content must be minor (formatting only) so that Tier 1 (exact anchor match) and Tier 3 (substring) fail.
- Default similarity threshold of 1.00 (or any threshold ≥ 0.99) triggers the `>` bug.

### Ruled Out
- **Session mode suppression:** The `is_session` flag does NOT suppress "Closest Match Diff" — the Jinja2 template renders validation errors unconditionally. Proven via full pipeline probe (Turn 13).
- **Report formatter truncation:** `build_failure_report(is_session=True)` preserves the full 835-char error message including diff. Proven via probe.
- **Edit matcher algorithm:** The `find_best_match` function itself works correctly — when a candidate is found, it produces the correct score and diff. The bug is in the heuristic cascade that filters candidates BEFORE the matcher sees them.

## Diagnostic Analysis

### Causal Model
The edit validation system uses a multi-tier heuristic cascade in `edit_matcher_heuristics.py` to efficiently find candidate start lines for matching a `FIND` block against file content:

1. **Tier 1 (Anchors):** Finds lines that exactly match the first/last line of the FIND block.
2. **Tier 2 (Fuzzy cascade):** Uses `SequenceMatcher.real_quick_ratio() > threshold` to find similar lines quickly.
3. **Tier 3 (Substring):** For single-line FIND blocks, checks `find_text in line`.
4. **Tier 4 (Exhaustive):** For files with <100 lines (`SMALL_FILE_LINE_LIMIT`), falls back to comparing every line.

The cascade has two independent guard bugs:
- **Bug A:** `>` should be `>=` in Tier 2. With default threshold 1.0, a score of 0.99 is never `> 1.0`, so Tier 2 is always disabled for threshold ≥ 0.99.
- **Bug B:** `SMALL_FILE_LINE_LIMIT = 100` is an arbitrary cutoff. Files with 100+ lines (like the 128-line `02-06-orchestrator-hardening.md`) bypass Tier 4 entirely.

When BOTH bugs are triggered (file ≥100 lines AND threshold ≥ 0.99), the cascade returns zero candidates, causing `find_best_match` to return `score=0.0` with no diff — even though the correct match exists.

### Discrepancies
1. **Early MRE passed with score 0.99.** The initial MRE used a 1-line test file → Tier 4 triggered (exhaustive search on <100 line file), bypassing the cascade entirely. This created a false negative: the matcher works fine, but the heuristic cascade blocked it in the real scenario. (Resolved: Proven via `09-probe-heuristic-cascade.py` against the real 128-line file.)
2. **"Session mode suppresses diff" hypothesis.** The Jinja2 template analysis showed no `is_session` guards around validation errors. The full pipeline probe confirmed the diff is preserved through `build_failure_report(is_session=True)` and `MarkdownReportFormatter.format()`. (Resolved: Falsified by probe in Turn 13.)

### Investigation History
1. **MRE creation.** Created `09-backtick-similarity-mre.py` with a 1-line file, confirmed `find_best_match` returns score 0.99 with diff. **Conclusion:** Matcher core works correctly.
2. **Full pipeline probe.** `09-probe-full-pipeline.py` traced `find_best_match_and_diff` → `_validate_single_edit` → `build_failure_report(is_session=True)` → `MarkdownReportFormatter.format()`. All four steps produce correct output with diff present. **Conclusion:** Session mode does NOT suppress the diff. Falsifies initial hypothesis.
3. **`_handle_logical_validation_errors` analysis.** Read `SessionOrchestrator._handle_logical_validation_errors` to trace how `ValidationError` objects become strings. Found no truncation. **Conclusion:** Error messages pass through intact.
4. **Heuristic cascade probe.** Created `09-probe-heuristic-cascade.py` that replicates the real scenario: 128-line file content with FIND text missing backticks. Result: all four tiers return empty candidates. Tier 2 disabled by `>` strictness, Tier 4 disabled by 100-line limit. **Conclusion:** Root cause identified — empty candidate set from heuristic cascade.
5. **Benchmark.** `09-benchmark-exhaustive.py` measured exhaustive search at 152ms for 1000-line files, confirming the limit can be safely removed. **Conclusion:** No performance justification for the 100-line limit.

## Solution
### Root Cause
Two guard conditions in `edit_matcher_heuristics.py`:
1. **`>` should be `>=`:** `_find_starts_by_fuzzy_cascade` uses `if matcher.real_quick_ratio() > threshold` instead of `>= threshold`. With default threshold 1.0, any match with score < 1.0 is rejected — including correct matches at 0.99.
2. **Arbitrary `SMALL_FILE_LINE_LIMIT = 100`:** Disables exhaustive search for files with 100+ lines. Benchmark shows exhaustive search takes only 152ms for a 1000-line file, making this limit unnecessary.

### Proven Fix (via Shadow File)
The fix consists of two changes to `src/teddy_executor/core/services/validation_rules/edit_matcher_heuristics.py`:
1. Change `>` to `>=` in the Tier 2 real_quick_ratio check.
2. Remove `SMALL_FILE_LINE_LIMIT` entirely (eliminate the 100-line cutoff).

The fix was verified via Shadow File methodology (Turn 29): a copy of `edit_matcher_heuristics.py` was modified and targeted by the MRE, which confirmed the fix resolves the symptom. No punctuation normalization or other logic changes are needed.

### Preventative Measures
- **Systemic Audit:** A `git grep` search for all `> threshold` patterns across the codebase found no other instances of strict greater-than being used for threshold comparisons. This class of bug is isolated to this single location.
- **Best Practice:** When implementing heuristic cascades with fallback tiers, ensure that the final tier (exhaustive) has no arbitrary size limit, or a limit high enough to cover realistic inputs. Performance profiling (benchmark) confirms no meaningful cost for eliminating the limit.
- **Recommendation:** For future heuristic cascade implementations, prefer inclusive comparisons (`>=`/`<=`) for threshold checks unless strict inequality has a documented semantic reason.
