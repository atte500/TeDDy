# RCA: `AttributeError` and `NameError` after Refactoring `PlanService`

## 1. Summary
The system experienced two distinct failures after refactoring the `PlanService` and its associated `Action` domain models.
1.  Unit tests in `tests/unit/core/services/test_plan_service.py` failed with `AttributeError: 'types.SimpleNamespace' object has no attribute 'command'`.
2.  Acceptance tests failed with `NameError: name 'file_path' is not defined` originating from the `_handle_create_file` method in `src/teddy/core/services/plan_service.py`.

## 2. Investigation
The investigation confirmed two primary hypotheses, each corresponding to one of the failure modes.

1.  **Hypothesis 1: Mock Factory Misconfiguration (Confirmed)**
    *   **Description:** The unit tests for `PlanService` use a mock `ActionFactory`. After the refactoring, the service expected `Action` objects to have direct attributes like `.command` and `.file_path`. However, the mocks in the tests were still configured to return objects with the old structure, where these values were nested inside a `.params` dictionary. This desynchronization caused the `AttributeError`.
    *   **Evidence:** The spike at `spikes/debug/01-verify-attribute-error/mre.py` successfully reproduced this issue in isolation.

2.  **Hypothesis 2: Incorrect Variable Reference (Confirmed)**
    *   **Description:** The `_handle_create_file` method in `PlanService` was correctly updated to use `action.file_path` for its core logic. However, the success message in the returned `ActionResult` still referred to a non-existent local variable `file_path`, causing the `NameError`.
    *   **Evidence:** The spike at `spikes/debug/02-verify-name-error/mre.py` successfully reproduced this issue in isolation.

## 3. Root Cause
The root cause is a multi-faceted but common refactoring error: an incomplete update. The change from a generic `Action` with a `params` dictionary to specific `Action` objects with direct attributes was not applied consistently across both production code and, crucially, the corresponding test mocks. This led to a contract breach between the `PlanService` and its mocked dependency in the unit tests, and a separate variable-level bug in the production code itself.

## 4. Recommended Action
A comprehensive fix requires updating both the service logic and the test mocks.
1.  In `src/teddy/core/services/plan_service.py`, correct the `NameError` in the `_handle_create_file` method.
2.  In `tests/unit/core/services/test_plan_service.py`, update all mock `ActionFactory` configurations to return `SimpleNamespace` objects with direct attributes (e.g., `command`, `file_path`, `content`) instead of a `params` dictionary.

A verifier script demonstrating both fixes is located at `spikes/debug/solution_verifier.py`. The Developer agent should use this as a guide to implement the corrections.
