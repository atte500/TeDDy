# Slice: EDIT Action Mismatch Indicator (00-03)

## Business Goal
Improve the diagnostic experience for users when an `EDIT` action fails due to a `FIND` block mismatch. By adding a clear `<-- MISMATCH` indicator to the first deviating line in the diff, we reduce the cognitive load required to identify subtle whitespace or indentation errors.

## Acceptance Criteria
- **Scenario: First Deviation Highlighted**
  - Given an `EDIT` action where the `FIND` block does not exactly match the file content.
  - When the plan is validated.
  - Then the `Closest Match Diff` in the error message MUST include the string `  <-- MISMATCH` appended to the **first line** that starts with a `-` (deletion) or `+` (addition).
  - And subsequent lines in the diff MUST NOT have the indicator.

## User Showcase
1. Create a file `test.txt` with content `line 1\nline 2`.
2. Execute a plan with an `EDIT` action on `test.txt`:
   - `FIND`: `line 1\nline 2 (typo)`
   - `REPLACE`: `line 1\nline 2 (fixed)`
3. Observe the validation error:
   ```text
   The `FIND` block could not be located in the file: test.txt
   ...
   **Closest Match Diff:**
   ```diff
     line 1
   - line 2 (typo)  <-- MISMATCH
   + line 2
   ```

## Architectural Changes
- **Modify:** `src/teddy_executor/core/services/validation_rules/edit.py`
  - Update the `_find_best_match_and_diff` helper function.
  - Iterate through the `difflib.ndiff` output and append `  <-- MISMATCH` to the first line starting with `- ` or `+ `.
  - Ensure `rstrip()` is used before appending to avoid trailing newline issues.

## Deliverables
- [ ] Updated `EditActionValidator` logic in `src/teddy_executor/core/services/validation_rules/edit.py`.
- [ ] Updated unit tests in `tests/unit/core/services/test_plan_validator.py` (specifically `test_validate_edit_provides_diff_on_mismatch`).
- [ ] Verified that `tests/integration/core/services/test_plan_validator_integration.py` still passes or is updated if necessary.
