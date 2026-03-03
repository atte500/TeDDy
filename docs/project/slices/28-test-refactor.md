# Slice 28: Standardize Test Suite

## Business Goal
Eliminate "Mocking Boilerplate" and ensure the test suite follows the standardized DI-based architecture. This rebalances the test pyramid by moving low-level logic verification to unit tests and keeping acceptance tests focused on CLI behavior.

## Acceptance Criteria
- [ ] `tests/conftest.py` provides `mock_edit_simulator`, `mock_inspector`, and `mock_report_formatter` fixtures.
- [ ] Every test in `tests/unit/` and `tests/integration/` resolves its system-under-test (SUT) via `container.resolve()`.
- [ ] Manual calls to `container.register()` and instantiations like `PlanValidator(...)` are removed from all test files (except `conftest.py`).
- [ ] Redundant acceptance tests are pruned, and the suite remains green.

## Architectural Changes
- **Dependency Injection:** Centralize all mock registration in `tests/conftest.py`.
- **Test Rebalancing:** Shift focus of `PlanValidator` and `MarkdownPlanParser` verification entirely to unit tests.

## Scope of Work
- [ ] **Infrastructure Enhancement:**
    - Update `tests/conftest.py` to include `mock_edit_simulator`, `mock_inspector`, and `mock_report_formatter`.
- [ ] **Unit Test Refactoring:**
    - `tests/unit/core/services/test_plan_validator.py`: Remove manual registration.
    - `tests/unit/core/services/test_execution_orchestrator.py`: Use shared fixtures.
    - `tests/unit/core/services/test_markdown_plan_parser.py`: Resolve from container.
    - `tests/unit/core/services/test_context_service.py`: Remove manual DI.
- [ ] **Integration Test Refactoring:**
    - `tests/integration/core/services/test_plan_validator_integration.py`: Standardize FS mock usage.
    - `tests/integration/adapters/outbound/test_web_searcher_adapter.py`: Remove manual registration.
- [ ] **Cleanup:**
    - Delete `tests/acceptance/test_refactored_core_service_execution.py`.
    - Delete `tests/acceptance/test_plan_execution_context.py`.
- [ ] **Verification:**
    - Run `poetry run pytest` to ensure no regressions.
