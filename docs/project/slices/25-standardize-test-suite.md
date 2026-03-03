# Slice 25: Standardize Test Suite

## Business Goal
Restore the integrity of the test suite by enforcing the "Pyramid" principle and standardizing DI usage. This reduces technical debt, prevents state leakage between tests, and improves the speed and reliability of unit tests.

## Acceptance Criteria
- [x] No `*_refactor.py` files exist in the codebase.
- [x] No unit tests (`tests/unit/`) instantiate `punq.Container()` manually.
- [x] All tests requiring DI use the centralized `container` fixture from `tests/conftest.py`.
- [x] `tests/unit/core/services/test_plan_validator.py` does not use `LocalFileSystemAdapter`.
- [x] All tests pass: `poetry run pytest`.

## User Showcase
Run the test suite and verify no files with the suffix `_refactor.py` are present. Check the source of the consolidated tests to confirm they resolve dependencies via the `container` fixture.

## Architectural Changes
- **Consolidation:** Merge `test_action_factory_refactor.py` into `test_action_factory.py`.
- **Consolidation:** Merge `test_plan_validator_refactor.py` into `test_plan_validator.py`.
- **Isolation:** Replace `LocalFileSystemAdapter` usage in `test_plan_validator.py` with `MagicMock(spec=IFileSystemManager)`.

## Scope of Work
- [x] **Action Factory Cleanup:**
    - Update `tests/unit/core/services/test_action_factory.py` to use the `container` fixture.
    - Port the `read` action resolution tests from the refactor file to the primary file.
    - Delete `tests/unit/core/services/test_action_factory_refactor.py`.
- [x] **Plan Validator Cleanup:**
    - Update `tests/unit/core/services/test_plan_validator.py` to use `MagicMock` instead of `LocalFileSystemAdapter`.
    - Note: Move any tests that *require* real filesystem interaction to `tests/integration/core/services/test_plan_validator_integration.py`.
    - Delete `tests/unit/core/services/test_plan_validator_refactor.py`.
- [x] **Global Audit:**
    - Verify no other manual `punq.Container()` calls remain in `tests/unit/`.

## Implementation Summary
The unit test suite has been successfully standardized to adhere to the "Test Pyramid" and centralized Dependency Injection principles.

- **Standardized DI:** All tests in `tests/unit/` now resolve dependencies through the centralized `container` fixture provided in `tests/conftest.py`. This eliminates state leakage and ensures consistency across the suite.
- **Consolidated Tests:** Redundant `*_refactor.py` files for `ActionFactory` and `PlanValidator` were merged into their primary counterparts.
- **Improved Isolation:** `PlanValidator` unit tests were refactored to use `MagicMock` for `IFileSystemManager` instead of `LocalFileSystemAdapter`. This ensures that business logic validation is tested independently of infrastructure.
- **Suite Integrity:** A global audit confirmed that manual `punq.Container()` calls have been eradicated from the unit test layer.
