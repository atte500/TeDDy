# Slice 26: Refactor Tests to Standardized DI

## Business Goal
To finalize the standardization of the test suite by ensuring all tests requiring dependency wiring use the centralized `container` fixture. This reduces maintenance overhead and ensures consistent behavior across unit, integration, and acceptance tests.

## Acceptance Criteria
- [ ] The following test files are refactored to use the `container` fixture instead of manual constructor calls:
    - `tests/unit/core/services/test_execution_orchestrator.py`
    - `tests/unit/core/services/test_context_service.py`
    - `tests/unit/core/services/test_plan_validator.py`
    - `tests/integration/core/services/test_execution_orchestrator.py`
    - `tests/integration/core/services/test_plan_validator_integration.py`
- [ ] Mocks are registered in the `container` within the tests as needed (using `container.register(Interface, instance=mock)`).
- [ ] All tests pass after refactoring (`poetry run pytest`).
- [ ] No manual imports of `punq` or direct service instantiations remain in these files.

## Architectural Changes
- Shift from Manual Dependency Injection to Container-based Injection in the specified test files to align with `ARCHITECTURE.md`.

## Scope of Work
- [ ] Update `tests/unit/core/services/test_execution_orchestrator.py` to use `container`.
- [ ] Update `tests/unit/core/services/test_context_service.py` to use `container`.
- [ ] Update `tests/unit/core/services/test_plan_validator.py` to use `container`.
- [ ] Update `tests/integration/core/services/test_execution_orchestrator.py` to use `container`.
- [ ] Update `tests/integration/core/services/test_plan_validator_integration.py` to use `container`.
