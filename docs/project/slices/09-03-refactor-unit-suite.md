# Slice 09-03: Refactor Unit Suite
- **Status:** Planned
- **Milestone:** [Milestone 09: Hexagonal Test Architecture](../milestones/09-hexagonal-test-architecture.md)
- **Specs:** N/A

## 1. Business Goal
Extend the benefits of the Test Harness Triad (Setup, Driver, Observer) to the unit test suite. This will eliminate setup rot, replace brittle string-based assertions with typed DTOs, and bring all unit test files into compliance with the project's mandatory 300 SLOC limit.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Refactor SLOC Offenders (Services)
**Goal:** Migrate the largest service unit tests to the harness and bring them under the 300-line limit.
- **Precondition:** Several service unit tests exceed 300 SLOC due to manual Markdown string setup.
- **Success Condition:** `tests/suites/unit/core/services/test_parser_advanced_actions.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_formatter_action_logs.py` uses `ReportParser` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_validator_edit.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_parser_errors.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_parser_metadata.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_execution_orchestrator.py` uses `TestEnvironment` and is < 300 SLOC.
#### Deliverables
- [ ] Refactor `tests/suites/unit/core/services/test_parser_advanced_actions.py` using `MarkdownPlanBuilder`.
- [ ] Refactor `tests/suites/unit/core/services/test_formatter_action_logs.py` using `ReportParser`.
- [ ] Refactor `tests/suites/unit/core/services/test_validator_edit.py` using `MarkdownPlanBuilder`.
- [ ] Refactor `tests/suites/unit/core/services/test_parser_errors.py` using `MarkdownPlanBuilder`.
- [ ] Refactor `tests/suites/unit/core/services/test_parser_metadata.py` using `MarkdownPlanBuilder`.
- [ ] Refactor `tests/suites/unit/core/services/test_execution_orchestrator.py` using `TestEnvironment`.

### Scenario 2: Standardize Unit Setup Patterns
**Goal:** Ensure all remaining unit tests utilize the `TestEnvironment` (Setup) for DI isolation.
- **Precondition:** Unit tests use a mix of manual mocking and ad-hoc setup.
- **Success Condition:** All unit tests in `tests/suites/unit/` use the `container` or `env` fixture for dependency management.
#### Deliverables
- [ ] Audit and refactor all remaining files in `tests/suites/unit/` to use the `container` or `env` fixture.

## 3. Architectural Changes
This slice propagates the **Test Harness Triad** pattern from the high-level suites into the unit suite.

- **Driver Migration:** Unit tests for parsers (`IPlanParser`) and validators (`IPlanValidator`) will migrate from hardcoded Markdown strings to the `MarkdownPlanBuilder`. This ensures that unit-level testing remains synchronized with the official protocol format.
- **Observer Migration:** Unit tests for formatters (`IMarkdownReportFormatter`) will migrate from manual regex assertions to the `ReportParser`. This allows formatters to be tested against a structured DTO representation of their output.
- **Setup Migration:** All unit tests will standardize on the `container` fixture for Dependency Injection, ensuring that unit tests are truly isolated and that mocks are correctly injected into the subjects under test.
