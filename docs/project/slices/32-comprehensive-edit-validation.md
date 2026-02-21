# Slice 32: Comprehensive EDIT Validation

## 1. Business Goal

As an AI Agent, I want the `PlanValidator` to report **all** `FIND` block failures within a single `EDIT` action, so that I can see the complete list of errors at once and correct my plan more efficiently. Currently, the validator stops checking an `EDIT` action after the first `FIND` block fails, hiding any other potential errors in the same action.

Additionally, I want the `EDIT` execution logic to automatically handle clean line deletion. When a `REPLACE` block is completely empty, the system should remove the targeted `FIND` block *and* its associated newline, preventing the accumulation of orphaned empty lines in the codebase.

## 2. Architectural Changes

We will modify the `PlanValidator` service to ensure its `_validate_edit_action` method iterates through all `FIND`/`REPLACE` pairs and collects all validation errors.
We will also modify the `EDIT` action execution logic (likely within `LocalFileSystemAdapter` or the file system port) to implement the smart newline deletion when a `REPLACE` block is perfectly empty.

-   **Modify:** `src/teddy_executor/core/services/plan_validator.py`
-   **Modify:** `src/teddy_executor/adapters/outbound/local_file_system_adapter.py`
-   **Create:** `tests/acceptance/test_comprehensive_validation.py`

## 3. Scope of Work

### Part 1: Report All Failures in a Single Action

#### 3.1. Create a Failing Acceptance Test

1.  **[x] Create a new test file** at `tests/acceptance/test_comprehensive_validation.py`.
2.  **[x] Add a new test case**, `test_edit_action_reports_all_find_block_failures`:
    -   Define a plan with a single `EDIT` action targeting `README.md`.
    -   The `EDIT` action must contain at least two `FIND`/`REPLACE` pairs, both with `FIND` blocks guaranteed not to exist.
    -   Execute the plan and assert that the command fails.
    -   Assert that the output contains the error messages for **both** failing `FIND` blocks.
3.  **[x] Run the test** and confirm it fails as expected.

#### 3.2. Implement the Architectural Change

This task requires a small refactoring of the `PlanValidator` to support collecting multiple errors from a single action validator.

1.  **[x] Modify the `validate` method** in `PlanValidator`:
    -   The current `try...except` block only captures the first error raised by a validator method. Change this logic.
    -   Instead of `try...except`, call the `validator_method` and expect it to return a list of `ValidationError` objects.
    -   Use `errors.extend()` to add all returned errors to the main list.
2.  **[x] Modify the `_validate_*_action` helper methods**:
    -   Change the signature of `_validate_create_action`, `_validate_read_action`, and `_validate_edit_action` to return `List[ValidationError]` instead of `None`.
    -   In `_validate_create_action` and `_validate_read_action`, wrap the existing logic in a `try...except PlanValidationError` block. On success, `return []`. On failure, catch the exception and `return [ValidationError(message=e.message, file_path=e.file_path)]`.
3.  **[x] Implement the core logic in `_validate_edit_action`**:
    -   At the beginning of the method, create an empty list, `action_errors: List[ValidationError] = []`.
    -   Inside the `for edit in edits:` loop, for each validation check (`find_block == replace_block`, `matches == 0`, `matches > 1`), **append** a `ValidationError` object to `action_errors` instead of raising an exception.
    -   At the end of the method, `return action_errors`.

#### 3.3. Verify the Fix

1.  **[x] Re-run the acceptance test** and confirm it now passes.

---

### Part 2: Enhance "Not Found" Errors with a Diff

#### 3.4. Create a Failing Acceptance Test for Diff Feedback

1.  **[x] Create a new test file** at `tests/acceptance/test_edit_validation_feedback.py`. *(Note: implemented in `test_comprehensive_validation.py`)*
2.  **[x] Add a new test case**, `test_edit_action_with_no_match_provides_diff`:
    -   Define a plan with an `EDIT` action targeting a file.
    -   The `FIND` block should have a subtle, one-character difference from the actual content.
    -   Execute the plan and assert that the command fails.
    -   Assert that the output report contains a `diff` block that clearly highlights the character-level mismatch.

#### 3.5. Implement Diff Generation Logic

1.  **[x] Modify `_validate_edit_action`** in `src/teddy_executor/core/services/plan_validator.py`.
2.  **[x] Import the `difflib` module**.
3.  **[x] Create a new private helper method**, `_find_best_match_and_diff(self, file_content: str, find_block: str) -> str`.
    -   This method will encapsulate the "sliding window" and `SequenceMatcher` logic from our spike to find the best match.
    -   It will then use `difflib.ndiff` to generate and return a high-clarity diff string.
4.  **[x] In `_validate_edit_action`**, within the `if matches == 0:` block, call this new helper method.
5.  **[x] Raise the `PlanValidationError`** with a new, rich error message that includes the generated diff.

#### 3.6. Verify the Fix

1.  **[x] Re-run the acceptance test** from step 3.4 and confirm it now passes.

---

### Part 3: Clean Line Deletion for Empty REPLACE Blocks

#### 3.7. Create a Failing Acceptance Test
1.  **[x] Create a new test case** in an appropriate acceptance test file (e.g., `tests/acceptance/test_edit_action_refactor.py` or a new one).
2.  **[x]** Define a plan with an `EDIT` action where the `REPLACE` block is perfectly empty (`""`).
3.  **[x]** Assert that the resulting file does not contain an orphaned empty line where the target text used to be.

#### 3.8. Implement Smart Newline Deletion
1.  **[x] Locate the `EDIT` execution logic** (e.g., `edit_file` in `LocalFileSystemAdapter`).
2.  **[x]** Before performing the standard `content.replace(find_block, replace_block)`, check if `replace_block == ""`.
3.  **[x]** If true, attempt to match and replace `find_block + '\n'` first. If that doesn't match, fall back to `find_block`. (Consider cross-platform compatibility, though Python's text mode usually normalizes to `\n`).
4.  **[x]** Ensure this logic correctly removes the line without leaving a gap.

#### 3.9. Verify the Fix
1.  **[x] Re-run the acceptance test** and confirm it passes.

## 4. Acceptance Criteria

### Scenario 1: An `EDIT` action with multiple invalid `FIND` blocks is validated

-   **Given** a `plan.md` file with a single `EDIT` action targeting an existing file.
-   **And** the `EDIT` action contains a `FIND` block for "NonExistentText1" and another `FIND` block for "NonExistentText2".
-   **When** I run `teddy execute` on that plan.
-   **Then** the command should fail.
-   **And** the output report must contain a validation error for "NonExistentText1".
-   **And** the output report must also contain a validation error for "NonExistentText2".

### Scenario 2: An `EDIT` action with a mismatched `FIND` block is validated

-   **Given** a file containing the text "This is the original content".
-   **And** a `plan.md` with an `EDIT` action targeting that file.
-   **And** the `EDIT` action's `FIND` block contains "This is the orignal content" (note the typo).
-   **When** I run `teddy execute` on that plan.
-   **Then** the command should fail.
-   **And** the output report must contain a validation error that includes a `diff` clearly highlighting the "original" vs. "orignal" discrepancy.

### Scenario 3: An `EDIT` action with an empty `REPLACE` block leaves no orphaned empty line

-   **Given** a file containing three lines of text.
-   **And** a `plan.md` with an `EDIT` action targeting that file.
-   **And** the `EDIT` action's `FIND` block targets the exact text of the second line.
-   **And** the `EDIT` action's `REPLACE` block is completely empty.
-   **When** I run `teddy execute` on that plan.
-   **Then** the command should succeed.
-   **And** the resulting file should contain only the first and third lines, with no empty line between them.
