# Vertical Slice 05: Refactor Test Setup

### 1. Business Goal

Improve the maintainability and reduce the brittleness of the unit test suite for the core application services. By centralizing the setup of the `PlanService` and its dependencies using shared `pytest` fixtures, future changes to the service's constructor will no longer require manually updating every single test case. This investment in code quality will speed up future feature development and refactoring by making the test suite more resilient to change.

### 2. Acceptance Criteria (Scenarios)

This is a refactoring slice, so the goal is to improve internal quality without changing external behavior.

**Scenario 1: All Existing Tests Pass**
- **Given:** The current suite of unit tests for `PlanService`.
- **When:** The test setup is refactored to use centralized `pytest` fixtures from a new `conftest.py` file.
- **Then:** All existing tests for `PlanService` must continue to pass without any change to the test logic itself.

**Scenario 2: Future Changes are Simplified (Verification)**
- **Given:** The refactored test suite with centralized fixtures.
- **When:** A developer adds a new, mocked dependency to the `PlanService` constructor.
- **Then:** Only the central test fixture in `conftest.py` needs to be updated to provide the new mock.
- **And:** The existing unit tests do not require individual modifications to their setup.

### 3. Interaction Sequence

Not applicable for a technical refactoring slice.

### 4. Scope of Work (Components)

- [ ] `Technical Refactoring`: Modify `tests/unit/core/services/test_plan_service.py` to remove local setup and use shared fixtures.
- [ ] `Technical Refactoring`: Create `tests/unit/core/services/conftest.py` to house the shared `pytest` fixtures for `PlanService` and its mocked dependencies.
