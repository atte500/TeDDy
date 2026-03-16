- **Status:** Resolved
- **MRE:** [tests/acceptance/test_validation_performance.py](/tests/acceptance/test_validation_performance.py)

## 1. Summary
The `execute` command failed to meet its 500ms performance budget when performing fuzzy `EDIT` matching on large files (500 lines). In CI environments, the execution took ~690ms. This degraded the responsiveness of the CLI and triggered a Jidoka "Stop the line" event in the CI pipeline.

## 2. Investigation Summary
A series of diagnostic spikes revealed two primary bottlenecks:
1. **Algorithmic Inefficiency:** The `edit_matcher.py` utility was joining lines into strings for `difflib.SequenceMatcher`, leading to slow character-level matching (~60ms per 100-line window).
2. **Startup Latency:** The `mistletoe` library was being imported at the module level in multiple core services, consuming ~175ms during every app startup. This violated ARCHITECTURE.md Rule #13 regarding lazy imports.

A high-fidelity spike confirmed that switching to line-based matching reduced the total command execution time from ~0.69s to under 0.1s.

## 3. Root Cause
The immediate technical cause was the use of `difflib.SequenceMatcher` on large joined strings, which is computationally expensive. The systemic cause was a regression in the enforcement of the "Lazy Import" architectural rule, specifically allowing `mistletoe` to be imported eagerly by the `MarkdownPlanParser` and its infrastructure.

## 4. Verified Solution
The solution is a two-part optimization:

### 4.1. Optimized Matcher
Update `src/teddy_executor/core/services/validation_rules/edit_matcher.py` to pass lists of lines directly to `SequenceMatcher`.

```python
def _evaluate_candidates(
    file_lines: List[str],
    find_lines: List[str],
    candidate_starts: Set[int],
    find_block: str,
) -> List[str]:
    # ...
    for start in candidate_starts:
        window = file_lines[start : start + num_find_lines]
        # PASS LISTS, NOT JOINED STRINGS
        matcher = difflib.SequenceMatcher(None, window, find_lines)
        ratio = matcher.ratio()
        # ...
```

### 4.2. Lazy Load Mistletoe
Move `import mistletoe` inside the `parse` method of `MarkdownPlanParser` and all other core services (`parser_infrastructure.py`, `parser_reporting.py`, etc.). Use `TYPE_CHECKING` for type hints to keep startup lean.

## 5. Preventative Measures
1. **Performance Regression Tests:** The failing test `test_validation_performance_on_large_files` has been optimized and should remain a permanent part of the suite.
2. **Startup Time Monitoring:** Consider adding a CI check that measures the minimum startup time of `teddy --version` to ensure it remains under 200ms.
3. **Lazy Import Linting:** Use `vulture` or custom ruff rules to detect non-lazy imports of known "heavy" libraries.

## 6. Recommended Regression Test
The test `tests/acceptance/test_validation_performance.py::test_validation_performance_on_large_files` is the definitive regression test for this fix.
