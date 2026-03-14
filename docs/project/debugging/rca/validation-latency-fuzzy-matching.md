# RCA: Validation Latency in Fuzzy Matching
- **Status:** Resolved
- **MRE:** N/A (Performance degradation report)

## 1. Summary
Validation of plans containing large `EDIT` actions (e.g., updating 100+ line prompt files) took an unacceptably long time (3.6s per block, ~15-20s for a 4-action plan). This latency occurred during the pre-flight validation phase, specifically when a `FIND` block failed to match exactly and the system attempted to find the "closest match" for diagnostic purposes.

## 2. Investigation Summary
- **Symptom:** `PlanValidator.validate()` hangs for seconds when processing large `EDIT` blocks.
- **Hypothesis:** The `difflib.SequenceMatcher.ratio()` call used in a sliding window in `_find_best_match_and_diff` is O(N*M) and too slow for large inputs.
- **Verification:**
    - A performance spike using real project data (`prompts/dev.xml`) confirmed a 3.6s latency for a single 70-line `FIND` block.
    - Verified that `difflib` performance degrades quadratically as line counts increase.
- **Optimization Exploration:**
    - Tested exact line indexing (Anchors).
    - Tested a multi-layered heuristic combining anchors with an incremental fuzzy cascade (searching for the first line fuzzy-style) and size-aware sub-sampling.
    - **Result:** The Multi-Layered Heuristic achieved a **310x speedup** (0.01s) with identical diagnostic results.

## 3. Root Cause
- **Immediate Cause:** The `EditActionValidator` used an exhaustive sliding window search to calculate similarity ratios for every possible position in a file. For a file of $N$ lines and a block of $M$ lines, this performed $N-M$ expensive `difflib` operations.
- **Systemic Cause:** Diagnostic helpers were designed to prioritize helpfulness (finding the best possible match) without regard for the computational cost when handling unusually large inputs (prompts/XML rulesets).

## 4. Verified Solution
The solution is a **Multi-Layered Heuristic** implemented in `src/teddy_executor/core/services/validation_rules/edit.py`:
1.  **Tier 1 (Exact Priority Anchors):** Index the file and match the 5 longest unique lines from the `FIND` block. Identify candidate windows based on these exact matches.
2.  **Tier 2 (Incremental Fuzzy Cascade):** If Tier 1 fails, fuzzy-match the *first* line of the `FIND` block against the file to find candidate starting points.
3.  **Tier 3 (Size-Aware Sub-Sampling):** For blocks > 20 lines, perform a quick "check-in" by comparing 10 representative lines. Only if the sample looks promising, execute the full, expensive `difflib.ratio()` calculation.

### Proven Code Snippet:
````python
def optimized_find_best_match_and_diff(file_content: str, find_block: str) -> str:
    file_lines = file_content.splitlines(keepends=True)
    find_lines = find_block.splitlines(keepends=True)
    num_find_lines = len(find_lines)

    # 1. Anchor-based pre-filtering (Fast Path)
    candidate_starts = _find_candidate_windows(file_lines, find_lines)

    # 2. Sub-sampled verification before full ratio (Diagnostic Optimization)
    best_ratio = 0.0
    best_match_lines = []
    for start in candidate_starts:
        window = file_lines[start : start + num_find_lines]
        if num_find_lines > 20 and not _quick_sample_check(window, find_lines):
            continue

        matcher = difflib.SequenceMatcher(None, "".join(window), find_block)
        ratio = matcher.ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match_lines = window
    # ... generate diff ...
````

## 5. Preventative Measures
- **Performance Budget:** Establish a performance budget for validation rules (< 100ms per action).
- **Heuristic Pattern:** Mandate tiered heuristic approaches for any diagnostic logic involving expensive string/sequence comparisons on potentially large files.

## 6. Recommended Regression Test
An integration test in `tests/integration/core/services/test_plan_validator_performance.py` that validates a plan with a 100+ line `EDIT` block against a 500+ line file and asserts that the validation completes in under **500ms**.
