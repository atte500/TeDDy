# Slice 32: Comprehensive EDIT Validation

## 1. Business Goal

As an AI Agent, I want the `PlanValidator` to report **all** `FIND` block failures within a single `EDIT` action, so that I can see the complete list of errors at once and correct my plan more efficiently.

Currently, the validator stops checking an `EDIT` action after the first `FIND` block fails, hiding any other potential errors in the same action.

## 2. Architectural Changes

We will modify the `PlanValidator` service to ensure its `_validate_edit_action` method iterates through all `FIND`/`REPLACE` pairs and collects all validation errors, rather than raising an exception on the first failure.

-   **Modify:** `src/teddy_executor/core/services/plan_validator.py`
-   **Create:** `tests/acceptance/test_comprehensive_validation.py`

## 3. Scope of Work

### 3.1. Create a Failing Acceptance Test

1.  **Create a new test file** at `tests/acceptance/test_comprehensive_validation.py`.
2.  **Add a new test case**, `test_edit_action_reports_all_find_block_failures`, that follows the pattern established by our spike:
    -   It should use `plan_content` to define a plan with a single `EDIT` action targeting `README.md`.
    -   This `EDIT` action must contain at least two `FIND`/`REPLACE` pairs.
    -   Both `FIND` blocks must contain unique text that is guaranteed not to exist in `README.md`.
    -   The test should execute `teddy execute` with this plan.
    -   Assert that the command fails (non-zero exit code).
    -   Assert that the captured `stdout` contains the error messages for **both** of the failing `FIND` blocks.
3.  **Run the test** and confirm that it fails as expected, because the current implementation only reports the first error.

### 3.2. Implement the Logic Change

1.  **Modify `_validate_edit_action`** in `src/teddy_executor/core/services/plan_validator.py`.
2.  **Introduce a local `errors` list** at the beginning of the `if isinstance(edits, list):` block.
3.  **Change the loop** (`for edit in edits:`) so that instead of `raise PlanValidationError`, it appends a new `PlanValidationError` instance to the local `errors` list for each failed validation check.
4.  **After the loop completes**, if the local `errors` list is not empty, `raise` all the collected errors. The existing `validate` method in the `PlanValidator` which calls `_validate_edit_action` already handles a `PlanValidationError` by appending it to a list of `ValidationError` objects. So we need to raise a `PlanValidationError` for each error found.
5.  **Ensure all `FIND` checks** (identical content, 0 matches, >1 matches) append to the list instead of raising immediately.

### 3.3. Verify the Fix

1.  **Re-run the acceptance test** from step 3.1.
2.  Confirm that the test now passes, as the report in `stdout` should contain the error messages for all failing `FIND` blocks.

## 4. Acceptance Criteria

### Scenario: An `EDIT` action with multiple invalid `FIND` blocks is validated

-   **Given** a `plan.md` file with a single `EDIT` action targeting an existing file.
-   **And** the `EDIT` action contains a `FIND` block for "NonExistentText1" and another `FIND` block for "NonExistentText2".
-   **When** I run `teddy execute` on that plan.
-   **Then** the command should fail.
-   **And** the output report must contain a validation error for "NonExistentText1".
-   **And** the output report must also contain a validation error for "NonExistentText2".
