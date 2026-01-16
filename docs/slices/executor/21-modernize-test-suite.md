# Vertical Slice: Modernize the Test Suite

*   **Source Brief**: [Brief 01: Comprehensive Refactoring](../../briefs/01-comprehensive-refactoring.md)

## Business Goal

To increase development velocity and reduce future maintenance costs by establishing a robust, standardized testing strategy. This work will eliminate brittle tests that rely on slow subprocesses and fragile string comparisons, making the entire test suite faster, more reliable, and easier for developers to work with.

## Acceptance Criteria (Scenarios)

### Scenario 1: Standardized "White-Box" Test Helper
*   **Given** a need to test a CLI command in an acceptance test
*   **When** the new standardized test helper is created and used
*   **Then** it provides a `typer.testing.CliRunner` instance and a consistent, in-process way to invoke the `teddy` CLI application for testing.

### Scenario 2: Refactored Acceptance Tests
*   **Given** the existing suite of acceptance tests
*   **When** they are refactored
*   **Then** all tests MUST use the new "white-box" helper, removing all dependencies on the old `subprocess`-based helpers.
*   **And** the entire test suite MUST pass.

### Scenario 3: Deprecation of Legacy Helpers
*   **Given** the old `subprocess`-based helpers in `tests/acceptance/helpers.py`
*   **When** the acceptance test refactoring is complete
*   **Then** the legacy helper functions ARE DELETED.

### Scenario 4: Focused and Aligned Unit Tests
*   **Given** the existing unit test suite
*   **When** it is refactored
*   **Then** all tests are aligned with the newly decomposed service classes (`PlanParser`, `ExecutionOrchestrator`, etc.), resulting in simpler, more focused tests with consistent fixture patterns.

## Architectural Changes

This is a technical refactoring slice focused entirely on the test suite. No production components will be created or modified. The primary architectural change is the formal implementation and enforcement of the testing patterns already defined in `docs/ARCHITECTURE.md`.

1.  **Standardize Acceptance Test Pattern:** All acceptance tests will be updated to use the `typer.testing.CliRunner` "white-box" pattern.
2.  **Unify Test Fixtures:** Test setup will be consolidated using standardized `pytest` fixtures where appropriate.
3.  **Deprecate Legacy Helpers:** The old `subprocess`-based test helpers will be removed from `tests/acceptance/helpers.py`.

## Interaction Sequence

1.  A new, centralized test helper function is created in `tests/acceptance/helpers.py` that sets up and provides a `typer.testing.CliRunner` for tests.
2.  Each acceptance test file is modified to use this new helper, replacing any calls to the old `subprocess` helpers.
3.  Once all acceptance tests are migrated, the old helper functions are removed.
4.  The unit test suite is reviewed and refactored to ensure tests are small, focused, and aligned with the new service boundaries established in the previous slice.

## Scope of Work

This checklist guides the refactoring of the test suite.

- [ ] **1. Review Documentation**
    - [ ] `READ` this slice document in its entirety.
    - [ ] `READ` the "Acceptance Testing for CLI Commands with Mocks" section in [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) to understand the "white-box" `CliRunner` pattern.

- [ ] **2. Implement Standardized Acceptance Test Helper**
    - [ ] `IMPLEMENT` a new, centralized helper function in `packages/executor/tests/acceptance/helpers.py` that instantiates and returns a `typer.testing.CliRunner`. This will be the single, standardized way to invoke the CLI application in acceptance tests.

- [ ] **3. Refactor Acceptance Test Suite**
    - [ ] `REFACTOR` all existing acceptance tests in `packages/executor/tests/acceptance/` to use the new `CliRunner` helper. Replace all calls to the old `subprocess`-based helpers. Ensure all tests parse structured output (like YAML) instead of asserting against raw strings.

- [ ] **4. Deprecate Legacy Helpers**
    - [ ] `DELETE` the old, `subprocess`-based helper functions from `packages/executor/tests/acceptance/helpers.py` now that they are no longer in use.

- [ ] **5. Refactor Unit Test Suite**
    - [ ] `REFACTOR` the unit tests in `packages/executor/tests/unit/` to align with the decomposed service layer. Focus on creating small, isolated tests with consistent and simple fixture patterns.

- [ ] **6. Update Feature Brief**
    - [ ] `EDIT` the feature brief at [`docs/briefs/01-comprehensive-refactoring.md`](../../briefs/01-comprehensive-refactoring.md) to mark "Slice 2: Modernize the Test Suite" as complete.
