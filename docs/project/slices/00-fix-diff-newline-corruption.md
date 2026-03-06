# Slice: Fix Closest Match Diff Corruption

## Business Goal
Ensure that the "Closest Match Diff" provided in validation errors is always readable and correctly formatted, even when the target code blocks or files do not end with a newline character.

## Acceptance Criteria
- [x] **Scenario: Diff lines are always separated by newlines**
  - Given a `FIND` block that does not end in a newline
  - And a file that does not end in a newline
  - When the validator generates a "Closest Match Diff"
  - Then each line of the diff (including `?` markers) must be on its own line in the output.

- [x] **Scenario: Intra-line markers are preserved**
  - Given a near-match with intra-line differences
  - When the diff is generated
  - Then the `?` markers from `difflib.ndiff` must be correctly aligned under the changed lines.

## Implementation Summary
The "Closest Match Diff" generator in `EditActionValidator` was corrected to handle inputs that lack trailing newlines. Previously, `"".join(diff)` caused lines without trailing `\n` (common for `difflib.ndiff` intra-line `?` markers or final lines) to collapse together. The implementation now explicitly strips existing newlines from each diff line and joins them with a standard `\n`.

**Key Changes:**
- Refactored `src/teddy_executor/core/services/validation_rules/edit.py::_find_best_match_and_diff` to use `"\n".join(line.rstrip("\n\r") for line in diff)`.
- Added a regression test `test_validate_edit_diff_handling_no_trailing_newline` in `tests/unit/core/services/test_plan_validator.py`.
- Resolved `PLR2004` linting issues in the new test code.

## Architectural Changes
- Modify `src/teddy_executor/core/services/validation_rules/edit.py`:
  - Update `_find_best_match_and_diff` to ensure newlines are consistently applied when joining the results of `difflib.ndiff`.

## Deliverables
- A fix in `edit.py` that handles newline-agnostic joining of diff lines.
- A new unit test in `tests/unit/core/services/test_plan_validator.py` (or a dedicated file) that reproduces the "collapsed line" bug with a non-newline-terminated input and verifies the fix.
