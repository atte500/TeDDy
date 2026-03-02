# Slice 21: Standardize DI Testing Infrastructure

## Business Goal
Reduce test maintenance overhead and boilerplate by centralizing Dependency Injection management.

## Acceptance Criteria
- [ ] A `container` fixture exists in `tests/conftest.py`.
- [ ] The fixture automatically patches `teddy_executor.__main__.container` using `monkeypatch`.
- [ ] `tests/integration/adapters/inbound/test_cli_adapter.py` is refactored to use the fixture, removing `fresh_container` and manual patching.
- [ ] `tests/acceptance/test_quality_of_life_improvements.py` is refactored to use the fixture.
- [ ] All existing tests pass.

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
