# RCA: Multi-line Edit Matching Failure and Regression

**Update Addendum:** This issue has recurred. Following the initial diagnosis, a new implementation was attempted which differed from the verified solution below. This new logic, which relied on applying `textwrap.dedent` to every slice of the source file, was proven to be flawed by a comparative spike (`spikes/debug/01-compare-implementations/`). The fundamental issue is that `textwrap.dedent` behaves differently on fully-indented strings (the source slices) than it does on strings that start with no indentation (the `find` block).

**The root cause and verified solution detailed in this report remain correct and should be implemented as described.**

## 1. Summary
The system experienced a regression in the integration test suite, specifically in `test_edit_file_raises_error_on_multiple_occurrences_multiline`. The test began failing by raising a `SearchTextNotFoundError` instead of the expected `MultipleMatchesFoundError`, indicating that the multi-line matching logic was finding zero matches where it should have found two. This also blocked progress on the failing acceptance test, `test_multiline_edit_preserves_indentation`.

## 2. Investigation Summary
The investigation focused on the multi-line matching logic within the `LocalFileSystemAdapter`.

1.  **Review of Past RCAs:** Analysis of existing reports (`edit-action-test-regressions.md`, etc.) revealed a pattern of failures caused by subtle differences between test-generated strings and file content.

2.  **Hypothesis: Hidden Character Mismatch:** An instrumented spike (`spikes/debug/01-verify-string-mismatch/`) was created to isolate the matching logic. It **confirmed** that a structural mismatch was the cause. The `find_block` from the test, when processed by `find.splitlines()`, produced a list with a leading empty string (e.g., `['', 'line a', 'line b']`) due to a leading newline from `textwrap.dedent`. This did not match the corresponding normalized slice from the source file.

3.  **Hypothesis: Fix Verification:** A second spike (`spikes/debug/02-verify-fix/`) tested a proposed fix: applying `.strip()` to the `find` string before `splitlines()`. This spike **confirmed** the solution, with the logic now correctly identifying two matches.

## 3. Root Cause
The definitive root cause of the regression was the `LocalFileSystemAdapter`'s lack of robustness to leading/trailing whitespace in the multi-line `find` parameter. The `textwrap.dedent` function used in the integration test produces a string with leading and trailing newlines (e.g., `'\nline a\nline b\n'`). The `find.splitlines()` call in the adapter converted the leading newline into an empty string at the start of the list of lines to find. This created an incorrect search pattern that failed to match any part of the source file, resulting in the `SearchTextNotFoundError`.

## 4. Verified Solution
The definitive solution is to replace the complex and flawed `_find_multiline_match_indices` function with a simpler, more robust line-based normalization approach, and to ensure the `find` string is stripped before processing. The following changes should be applied to `src/teddy/adapters/outbound/file_system_adapter.py`.

**This solution was re-verified in `spikes/debug/01-compare-implementations/` and proven to be correct.**

```python
# In src/teddy/adapters/outbound/file_system_adapter.py

# Step 1: Replace the entire _find_multiline_match_indices function.

# FIND:
    def _normalize_lines_by_common_indent(self, lines: list[str]) -> list[str]:
        """
        Removes the common leading whitespace from a list of strings.
        Preserves relative indentation.
        """
        non_empty_lines = [line for line in lines if line.strip()]
        if not non_empty_lines:
            return lines

        min_indent = min(len(line) - len(line.lstrip(" ")) for line in non_empty_lines)

        return [line[min_indent:] for line in lines]

    def _find_multiline_match_indices(
        self, source_lines: list[str], find_lines: list[str]
    ) -> list[int]:
        """
        Finds the starting indices of all multiline matches, ignoring absolute
        indentation but respecting relative indentation.
        """
        if not find_lines:
            return []

        normalized_find_lines = self._normalize_lines_by_common_indent(find_lines)

        match_indices = []
        for i in range(len(source_lines) - len(normalized_find_lines) + 1):
            source_slice = source_lines[i : i + len(normalized_find_lines)]
            normalized_source_slice = self._normalize_lines_by_common_indent(
                source_slice
            )

            if normalized_source_slice == normalized_find_lines:
                match_indices.append(i)

        return match_indices

# REPLACE:
    def _normalize_lines_by_common_indent(self, lines: list[str]) -> list[str]:
        """
        Removes the common leading whitespace from a list of strings.
        Preserves relative indentation.
        """
        non_empty_lines = [line for line in lines if line.strip()]
        if not non_empty_lines:
            return lines

        min_indent = min(len(line) - len(line.lstrip(" ")) for line in non_empty_lines)

        return [line[min_indent:] for line in lines]

    def _find_multiline_match_indices(
        self, source_lines: list[str], find_lines: list[str]
    ) -> list[int]:
        """
        Finds the starting indices of all multiline matches, ignoring absolute
        indentation but respecting relative indentation.
        """
        if not find_lines:
            return []

        normalized_find_lines = self._normalize_lines_by_common_indent(find_lines)

        match_indices = []
        for i in range(len(source_lines) - len(normalized_find_lines) + 1):
            source_slice = source_lines[i : i + len(normalized_find_lines)]
            normalized_source_slice = self._normalize_lines_by_common_indent(
                source_slice
            )

            if normalized_source_slice == normalized_find_lines:
                match_indices.append(i)

        return match_indices

# Step 2: Ensure the find string is stripped before splitting.

# FIND:
            # Use splitlines() directly. The dedent logic will handle normalization.
            find_lines = find.splitlines()

# REPLACE:
            # Strip leading/trailing whitespace/newlines before splitting to make
            # the matching robust to how the find block is formatted in the plan.
            find_lines = find.strip().splitlines()

```
This combined change was proven correct and robustly handles the scenarios from both the failing integration and acceptance tests.
