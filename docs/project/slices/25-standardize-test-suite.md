# Slice 25: Standardize Test Suite

## Business Goal
Restore the integrity of the test suite by enforcing the "Pyramid" principle and standardizing DI usage. This reduces technical debt, prevents state leakage between tests, and improves the speed and reliability of unit tests.

## Acceptance Criteria
- [ ] No `*_refactor.py` files exist in the codebase.
- [ ] No unit tests (`tests/unit/`) instantiate `punq.Container()` manually.
- [ ] All tests requiring DI use the centralized `container` fixture from `tests/conftest.py`.
- [ ] `tests/unit/core/services/test_plan_validator.py` does not use `LocalFileSystemAdapter`.
- [ ] All tests pass: `poetry run pytest`.

## User Showcase
Run the test suite and verify no files with the suffix `_refactor.py` are present. Check the source of the consolidated tests to confirm they resolve dependencies via the `container` fixture.

## Architectural Changes
- **Consolidation:** Merge `test_action_factory_refactor.py` into `test_action_factory.py`.
- **Consolidation:** Merge `test_plan_validator_refactor.py` into `test_plan_validator.py`.
- **Isolation:** Replace `LocalFileSystemAdapter` usage in `test_plan_validator.py` with `MagicMock(spec=IFileSystemManager)`.

## Scope of Work
- [ ] **Action Factory Cleanup:**
    - Update `tests/unit/core/services/test_action_factory.py` to use the `container` fixture.
    - Port the `read` action resolution tests from the refactor file to the primary file.
    - Delete `tests/unit/core/services/test_action_factory_refactor.py`.
- [ ] **Plan Validator Cleanup:**
    - Update `tests/unit/core/services/test_plan_validator.py` to use `MagicMock` instead of `LocalFileSystemAdapter`.
    - Note: Move any tests that *require* real filesystem interaction to `tests/integration/core/services/test_plan_validator_integration.py`.
    - Delete `tests/unit/core/services/test_plan_validator_refactor.py`.
- [ ] **Global Audit:**
    - Verify no other manual `punq.Container()` calls remain in `tests/unit/`.
