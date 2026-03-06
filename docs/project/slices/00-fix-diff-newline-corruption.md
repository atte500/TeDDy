# Slice: Fix Closest Match Diff Corruption

## Business Goal
Ensure that the "Closest Match Diff" provided in validation errors is always readable and correctly formatted, even when the target code blocks or files do not end with a newline character.

## Acceptance Criteria
- **Scenario: Diff lines are always separated by newlines**
  - Given a `FIND` block that does not end in a newline
  - And a file that does not end in a newline
  - When the validator generates a "Closest Match Diff"
  - Then each line of the diff (including `?` markers) must be on its own line in the output.

- **Scenario: Intra-line markers are preserved**
  - Given a near-match with intra-line differences
  - When the diff is generated
  - Then the `?` markers from `difflib.ndiff` must be correctly aligned under the changed lines.

## Architectural Changes
- Modify `src/teddy_executor/core/services/validation_rules/edit.py`:
  - Update `_find_best_match_and_diff` to ensure newlines are consistently applied when joining the results of `difflib.ndiff`.

## Deliverables
- A fix in `edit.py` that handles newline-agnostic joining of diff lines.
- A new unit test in `tests/unit/core/services/test_plan_validator.py` (or a dedicated file) that reproduces the "collapsed line" bug with a non-newline-terminated input and verifies the fix.
