# Slice 28: Standardize Test Suite

## Business Goal
Eliminate "Mocking Boilerplate" and ensure the test suite follows the standardized DI-based architecture. This rebalances the test pyramid by moving low-level logic verification to unit tests and keeping acceptance tests focused on CLI behavior.

## Acceptance Criteria
- [x] `tests/conftest.py` provides `mock_edit_simulator`, `mock_inspector`, and `mock_report_formatter` fixtures.
- [x] Every test in `tests/unit/` and `tests/integration/` resolves its system-under-test (SUT) via `container.resolve()`.
- [x] Manual calls to `container.register()` and instantiations like `PlanValidator(...)` are removed from all test files (except `conftest.py`).
- [x] Redundant acceptance tests are pruned, and the suite remains green.

## Architectural Changes
- **Dependency Injection:** Centralize all mock registration in `tests/conftest.py`.
- **Test Rebalancing:** Shift focus of `PlanValidator` and `MarkdownPlanParser` verification entirely to unit tests.

## Scope of Work
- [x] **Infrastructure Enhancement:**
    - Update `tests/conftest.py` to include `mock_edit_simulator`, `mock_inspector`, and `mock_report_formatter`.
- [x] **Unit Test Refactoring:**
    - `tests/unit/core/services/test_plan_validator.py`: Remove manual registration.
    - `tests/unit/core/services/test_execution_orchestrator.py`: Use shared fixtures.
    - `tests/unit/core/services/test_markdown_plan_parser.py`: Resolve from container.
    - `tests/unit/core/services/test_context_service.py`: Remove manual DI.
- [x] **Integration Test Refactoring:**
    - `tests/integration/core/services/test_plan_validator_integration.py`: Standardize FS mock usage.
    - `tests/integration/adapters/outbound/test_web_searcher_adapter.py`: Remove manual registration.
- [x] **Cleanup:**
    - Delete `tests/acceptance/test_refactored_core_service_execution.py`.
    - Delete `tests/acceptance/test_plan_execution_context.py`.
- [x] **Verification:**
    - Run `poetry run pytest` to ensure no regressions.

## Implementation Summary
The test suite has been successfully standardized to follow a DI-based architecture.

### Key Refactorings
- **Centralized Infrastructure:** All common mocks and service registrations are now managed via `tests/conftest.py`, significantly reducing boilerplate in individual test files.
- **Unit & Integration Standardization:** Every unit and integration test now resolves its System-Under-Test (SUT) from the centralized `container` fixture. This ensures tests are always wired identically to production unless explicitly overridden.
- **Integration Container Pattern:** Formalized a pattern for integration tests where the production DI graph is selectively re-wired (e.g., swapping a `LocalFileSystemAdapter`'s root to a `tmp_path`) to validate real component interaction safely.
- **Legacy Cleanup:** Removed redundant acceptance tests and smoke tests that were originally used for infrastructure spiking, resulting in a leaner and faster test suite.

### Performance & Coverage
- **Status:** GREEN
- **Total Tests:** 230
- **Line Coverage:** 90%

### [NEW] Reminders for Next Cycle
- **Formalize Integration Pattern:** The `integration_container` pattern used in `test_plan_validator_integration.py` should be documented as the official standard for cross-component integration testing.
