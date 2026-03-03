# Slice 21: Standardize DI Testing Infrastructure

## Business Goal
Reduce test maintenance overhead and boilerplate by centralizing Dependency Injection management.

## Acceptance Criteria
- [x] A `container` fixture exists in `tests/conftest.py`.
- [x] The fixture automatically patches `teddy_executor.__main__.container` using `monkeypatch`.
- [x] `tests/integration/adapters/inbound/test_cli_adapter.py` is refactored to use the fixture, removing `fresh_container` and manual patching.
- [x] `tests/acceptance/test_quality_of_life_improvements.py` is refactored to use the fixture.
- [x] All existing tests pass.

## Implementation Summary
The DI testing infrastructure has been standardized across the project.

### Key Changes:
- **tests/conftest.py**: Introduced a centralized `container` fixture that automatically creates a fresh `punq.Container` and patches `teddy_executor.__main__.container` using `monkeypatch`.
- **tests/unit/test_di_fixture_smoke.py**: Added a permanent smoke test to verify the infrastructure.
- **tests/integration/adapters/inbound/test_cli_adapter.py**: Refactored to use the new fixture, removing redundant local `fresh_container` logic.
- **tests/acceptance/test_quality_of_life_improvements.py**: Refactored to use the new fixture, eliminating manual `with patch(...)` blocks and reducing test complexity.

### Benefits:
- **Reduced Boilerplate**: Standardizes how DI is handled in tests, making them cleaner and easier to read.
- **Improved Maintainability**: Changes to container creation now only need to be handled in one place.
- **Consistent State**: Ensures every test starts with a truly fresh container and proper monkeypatching, preventing cross-test state pollution.

## Architectural Changes
- **tests/conftest.py**: New `pytest` fixture.
- **tests/**: Targeted refactoring of integration and acceptance tests.

## Scope of Work
1.  **Add Fixture**:
    ```python
    @pytest.fixture
    def container(monkeypatch):
        from teddy_executor.container import create_container
        import teddy_executor.__main__

        c = create_container()
        monkeypatch.setattr(teddy_executor.__main__, "container", c)
        return c
    ```
2.  **Refactor CLI Adapter Test**: Remove the `fresh_container` fixture and the manual `patch` block in `test_cli_invokes_orchestrator_with_plan_file`.
3.  **Refactor QoL Test**: Remove the manual `patch("teddy_executor.__main__.container", test_container)` block.
4.  **Verification**: Run `pytest tests/integration tests/acceptance`.
