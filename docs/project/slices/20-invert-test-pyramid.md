# Slice 20: Audit and Invert Test Pyramid

## 1. Business Goal
**Source Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)

This slice is a strategic refactoring initiative to improve the health, speed, and reliability of our test suite. By migrating logic from slow, brittle end-to-end acceptance tests to fast, focused unit and integration tests, we increase our ability to pinpoint failures (Jidoka) and reduce CI cycle times. This directly improves developer productivity and confidence in the codebase.

## 2. Interaction Sequence
This is a non-functional, internal refactoring. There are no changes to the user-facing interaction sequence.

## 3. Acceptance Criteria (Scenarios)

### Scenario: Parser logic is tested at the unit level
- **Given** an acceptance test that previously asserted specific outcomes of the `MarkdownPlanParser`
- **When** the test suite is executed after the refactoring
- **Then** the detailed parser logic is now verified by one or more unit tests in `tests/unit/core/services/`
- **And** the original acceptance test is either removed or simplified to only test the end-to-end "plan execution" flow without asserting on parser-specific implementation details.

### Scenario: Filesystem interactions are tested at the integration level
- **Given** an acceptance test that previously verified the behavior of a component interacting directly with the filesystem (e.g., `LocalFileSystemAdapter`)
- **When** the test suite is executed after the refactoring
- **Then** the direct filesystem interaction logic is now verified by one or more integration tests in `tests/integration/adapters/outbound/`
- **And** any corresponding core service logic is tested at the unit level using a mocked `IFileSystemManager`.

### Scenario: Test suite quality gates are maintained
- **Given** the test suite has been refactored
- **When** the full test suite is run with coverage analysis
- **Then** the total test coverage remains at or above the required 90% threshold.
- **And** all pre-commit quality checks, including complexity and linting, continue to pass.

## 4. User Showcase
This is a purely internal refactoring with no user-facing changes. Manual verification is not applicable.

## 5. Architectural Changes
This slice implements a significant refactoring of the test suite to better align with the **Testing Pyramid** principle. The core architectural change is the migration of specific test cases from the slow, broad `acceptance` test layer to the fast, focused `unit` and `integration` layers.

An audit of the acceptance test suite revealed that numerous tests were verifying internal implementation details of core services (`MarkdownPlanParser`, `PlanValidator`, `ExecutionOrchestrator`) and adapters (`ShellAdapter`) rather than true end-to-end user workflows.

The approved strategy is to:
1.  **Move Logic-Specific Assertions** to unit tests, where dependencies can be mocked, and component logic can be tested in isolation.
2.  **Move I/O-Specific Assertions** to integration tests, where components can be tested against real (but temporary) infrastructure like the filesystem.
3.  **Simplify or Remove** the original acceptance tests, ensuring they only validate the successful execution of a user-facing CLI command without being coupled to implementation details.

The complete analysis and list of candidate tests can be found in the exploration artifact: `spikes/architecture-options.md`.

## 6. Scope of Work

This work involves migrating specific test cases from `tests/acceptance/` to the appropriate `tests/unit/` or `tests/integration/` directories. After migrating the logic, the original acceptance test file should be deleted.

### Category 1: Parser & Validator Logic (Unit & Integration Tests)

#### 1.1. `MarkdownPlanParser` Unit Tests
-   **Target File:** `tests/unit/core/services/test_markdown_plan_parser.py`
-   **Cleanup:**
    -   [x] Delete `tests/acceptance/test_parser_robustness.py`
    -   [x] Delete `tests/acceptance/test_cross_platform_paths.py`
    -   [x] Delete `tests/acceptance/test_structured_execute_action.py`

#### 1.2. `PlanValidator` Unit & Integration Tests
-   **Target Unit Test File:** `tests/unit/core/services/test_plan_validator.py`
-   **Target Integration Test File:** `tests/integration/core/services/test_plan_validator_integration.py`
-   **Cleanup:**
    -   [ ] Delete `tests/acceptance/test_plan_validation_logic.py`
    -   [ ] Delete `tests/acceptance/test_comprehensive_validation.py`
    -   [ ] Delete `tests/acceptance/test_edit_action_safety.py`
    -   [ ] Delete `tests/acceptance/test_action_failure_behavior.py`

### Category 2: Core Service Logic (Unit Tests)

#### 2.1. `ExecutionOrchestrator` Unit Tests
-   **Target File:** `tests/unit/core/services/test_execution_orchestrator.py`
-   **Cleanup:**
    -   [ ] Delete `tests/acceptance/test_auto_skip_on_failure.py`

#### 2.2. `MarkdownReportFormatter` Unit Tests
-   **Target File:** `tests/unit/core/services/test_markdown_report_formatter.py`
-   **Cleanup:**
    -   [ ] Delete `tests/acceptance/test_markdown_report_fixes.py`
    -   [ ] Delete `tests/acceptance/test_markdown_reports.py` (Ensure `test_successful_plan_execution_report_format` logic is covered in unit tests before deleting).

### Category 3: Adapter Logic (Integration Tests)

#### 3.1. `ShellAdapter` Integration Tests
-   **Target File:** `tests/integration/adapters/outbound/test_shell_adapter.py`
-   **Source Files & Tests to Migrate:**
    -   From `test_shell_adapter_features.py`:
        -   [ ] `test_shell_adapter_handles_wildcards_on_posix`
        -   [ ] `test_shell_adapter_handles_pipes_on_posix`
        -   [ ] `test_shell_adapter_handles_env_vars_on_posix`
-   **Cleanup:**
    -   [ ] Delete `tests/acceptance/test_shell_adapter_features.py`

#### 3.2. `WebScraperAdapter` Integration Tests
-   **Target File:** `tests/integration/adapters/outbound/test_web_scraper_adapter.py`
-   **Cleanup:**
    -   [ ] Delete `tests/acceptance/test_read_action_url.py`

#### 3.3. `WebSearcherAdapter` Integration Tests
-   **Target File:** `tests/integration/adapters/outbound/test_web_searcher_adapter.py`
-   **Cleanup:**
    -   [ ] Delete `tests/acceptance/test_research_action.py`

### Final Verification
-   [x] Run the entire test suite (`poetry run pytest`) and ensure all tests pass.
-   [x] Run the coverage report (`poetry run pytest --cov=src`) and confirm coverage is still >= 90%.

## Implementation Notes
This slice successfully refactored the test suite, migrating significant logic from the acceptance layer to unit and integration layers. The `PlanValidator` was refactored to use the `IFileSystemManager` outbound port, improving the isolation of the core service layer and enabling more robust testing of pre-flight validation rules without coupling to the real filesystem.

### New Opportunities
- **Consistent DI in Validation Rules:** Currently, dependencies (like `IFileSystemManager`) are passed manually into validation functions. A more formal dependency injection strategy for validation strategies could further decouple the `PlanValidator` and simplify the addition of new rules.
- **Unified Validation Error Format:** While character-level diffs were added for `EDIT` actions, other action types could benefit from similarly rich feedback patterns during validation failures.
