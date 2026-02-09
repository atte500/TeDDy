# Slice 11: Implement Smart Indentation for Edit Action

## Business Goal

To improve the robustness and reliability of the AI-driven workflow by making the `edit_file` action smarter. The current implementation requires the AI to perfectly calculate the indentation for any replacement code block, making plans brittle. This slice will refactor the `edit_file` logic to automatically handle indentation, reducing the cognitive load on the AI and making the system more resilient.

## Architectural Changes

The work is confined to the `LocalFileSystemAdapter` and does not introduce new components or change existing contracts.

-   **Component to Modify:** `src/teddy_executor/adapters/outbound/local_file_system_adapter.py`
    -   The `_apply_single_edit` method will be completely refactored to use a new, robust, regex-based indentation handling logic.
    -   The following now-obsolete helper methods will be **deleted**:
        -   `_normalize_lines_by_common_indent`
        -   `_find_multiline_match_indices`
        -   `_reconstruct_content`

## Scope of Work

-   **[ ] Task 1: Add Imports**
    -   In `src/teddy_executor/adapters/outbound/local_file_system_adapter.py`, add the following imports at the top of the file:
        ```python
        import re
        import textwrap
        ```

-   **[ ] Task 2: Refactor `_apply_single_edit` Method**
    -   Replace the entire body of the `_apply_single_edit` method with the new, verified logic. The new implementation must handle both single-line and multi-line edits and should intelligently calculate and apply indentation to the `replace` block. Refer to the logic in the `spikes/spike_smart_indent.py` file for the canonical implementation.

-   **[ ] Task 3: Remove Dead Code**
    -   Delete the following unused private methods from the `LocalFileSystemAdapter` class:
        -   `_normalize_lines_by_common_indent`
        -   `_find_multiline_match_indices`
        -   `_reconstruct_content`

-   **[ ] Task 4: Verify Existing Tests**
    -   Run the existing integration tests for the adapter to ensure they still pass with the new logic. The public contract of `edit_file` has not changed, so the existing tests in `tests/integration/adapters/outbound/test_file_system_adapter.py` should pass without modification.

## Acceptance Criteria

-   All changes must be implemented in `src/teddy_executor/adapters/outbound/local_file_system_adapter.py`.
-   The three specified helper methods must be removed.
-   The `_apply_single_edit` method must contain the new, smarter indentation logic.
-   All existing tests in `tests/integration/adapters/outbound/test_file_system_adapter.py` must pass after the refactoring.
