# Slice 09-02: Refactor Acceptance & Integration Suites
- **Status:** Planned
- **Milestone:** [Milestone 09: Hexagonal Test Architecture](../milestones/09-hexagonal-test-architecture.md)
- **Specs:** N/A

## 1. Business Goal
Migrate the existing acceptance and integration test suites to use the formal Test Harness Triad (Setup, Driver, Observer). This migration will eliminate thousands of lines of duplicated Markdown strings, improve test readability, and bring the test suite into compliance with the project's strict 300 SLOC limit.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Establish Symmetrical Test Harness [✓]
**Goal:** Create a complete, exhaustive harness for driving the system and verifying outcomes.
- **Precondition:** Test setup and verification are ad-hoc and heavily reliant on manual string manipulation.
- **Success Condition:** `MarkdownPlanBuilder` (Driver) is exhaustive, supporting all 9 action types and protocol flags.
- **Success Condition:** `ReportParser` (Observer) is implemented, allowing tests to parse CLI output back into typed DTOs.
- **Success Condition:** `CliTestAdapter` is refactored to orchestrate the builder and parser, providing a "One-Liner" API for test cases: `adapter.execute(plan).assert_action_success(0)`.
- **Success Condition:** `TestEnvironment` (Setup) harness is implemented, encapsulating DI patching and workspace setup.
#### Deliverables
- [✓] Exhaustive `MarkdownPlanBuilder` in `tests/drivers/plan_builder.py`.
- [✓] `ReportParser` in `tests/observers/report_parser.py`.
- [✓] `CliTestAdapter` in `tests/drivers/cli_adapter.py`.
- [✓] `TestEnvironment` harness in `tests/setup/test_environment.py`.
- [✓] Update Design Documents for all new harness components.

#### Implementation Notes
Scenario 1 established the formal Test Harness Triad. The `MarkdownPlanBuilder` now supports all 9 action types with specialized fluent methods. The `ReportParser` provides a robust, regex-based observer for CLI output. The `CliTestAdapter` orchestrates in-process CLI execution, and the `TestEnvironment` ensures isolation and workspace anchoring for every test run. Unit tests for all harness components are located in `tests/unit/`.

### Scenario 2: Refactor ALL Acceptance Tests [✓]
**Goal:** Replace hardcoded plan strings and manual CLI invocation logic across the entire acceptance suite.
- **Precondition:** Many tests use `textwrap.dedent` for plans and manual `CliRunner` calls.
- **Success Condition:** ALL files in `tests/acceptance/` are refactored to use `MarkdownPlanBuilder`.
- **Success Condition:** ALL refactored files do not exceed the 300 SLOC limit.
#### Deliverables
- [✓] `tests/acceptance/test_action_isolation.py`
- [✓] `tests/acceptance/test_ai_telemetry.py`
- [✓] `tests/acceptance/test_all_validation_errors_show_ast.py`
- [✓] `tests/acceptance/test_auto_initialization.py`
- [✓] `tests/acceptance/test_change_preview_feature.py`
- [✓] `tests/acceptance/test_cli_polish.py`
- [✓] `tests/acceptance/test_cli_ux_improvements.py`
- [✓] `tests/acceptance/test_context_aware_editing.py`
- [✓] `tests/acceptance/test_context_command_refactor.py`
- [✓] `tests/acceptance/test_create_overwrite.py`
- [✓] `tests/acceptance/test_edit_multi_block_transparency.py`
- [✓] `tests/acceptance/test_edit_transparency_and_bulk.py`
- [✓] `tests/acceptance/test_edit_ux_polish.py`
- [✓] `tests/acceptance/test_enhanced_validation.py`
- [✓] `tests/acceptance/test_execute_granular_failure.py`
- [✓] `tests/acceptance/test_generalized_clipboard_output.py`
- [✓] `tests/acceptance/test_hanging_command_management.py`
- [✓] `tests/acceptance/test_interactive_execution.py`
- [✓] `tests/acceptance/test_cli_polish.py`
- [✓] `tests/acceptance/test_non_interactive_orchestration.py`
- [✓] `tests/acceptance/test_parser_polish.py`
- [✓] `tests/acceptance/test_progress_logging.py`
- [✓] `tests/acceptance/test_prompt_action.py`
- [✓] `tests/acceptance/test_quality_of_life_improvements.py`
- [✓] `tests/acceptance/test_redundant_edit_hints.py`
- [✓] `tests/acceptance/test_relax_execute_protocol.py`
- [✓] `tests/acceptance/test_report_enhancements.py`
- [✓] `tests/acceptance/test_session_management.py`
- [✓] `tests/acceptance/test_session_resume_robustness.py`
- [✓] `tests/acceptance/test_similarity_threshold_config.py`
- [✓] `tests/acceptance/test_streamlined_init.py`
- [✓] `tests/acceptance/test_validation_performance.py`
- [✓] `tests/acceptance/test_walking_skeleton.py`

#### Implementation Notes (Scenario 2)
- Refactored the entire acceptance test suite (87 tests) to use the Test Harness Triad.
- Standardized workspace isolation and DI patching using `TestEnvironment`.
- Replaced manual `CliRunner` usage with `CliTestAdapter` for robust CLI orchestration.
- Migrated all hardcoded Markdown plan strings to the fluent `MarkdownPlanBuilder` DSL.
- Fixed several brittle regressions in existing tests caused by direct filesystem manipulation or missing mocks.
- Verified performance requirements in `test_validation_performance.py` (< 500ms).

### Scenario 3: Refactor ALL Integration Tests [✓]
**Goal:** Ensure all integration tests use the `TestComposition` (punq-based) fixture and standardized mocks.
- **Precondition:** Integration tests have inconsistent mocking and setup strategies.
- **Success Condition:** ALL files in `tests/integration/` use the `container` fixture and global mocks (e.g., `mock_fs`).
- **Success Condition:** ALL refactored files do not exceed the 300 SLOC limit.
#### Deliverables
- [✓] `tests/integration/adapters/inbound/test_cli_adapter.py`
- [✓] `tests/integration/adapters/inbound/test_cli_formatting_integration.py`
- [✓] `tests/integration/adapters/outbound/test_console_interactor_editor.py`
- [✓] `tests/integration/adapters/outbound/test_console_interactor_headers.py`
- [✓] `tests/integration/adapters/outbound/test_file_system_adapter.py`
- [✓] `tests/integration/adapters/outbound/test_local_repo_tree_generator.py`
- [✓] `tests/integration/adapters/outbound/test_shell_adapter.py`
- [✓] `tests/integration/adapters/outbound/test_system_environment_inspector.py`
- [✓] `tests/integration/adapters/outbound/test_tree_generator_performance.py`
- [✓] `tests/integration/adapters/outbound/test_web_scraper_adapter.py`
- [✓] `tests/integration/adapters/outbound/test_web_searcher_adapter.py`
- [✓] `tests/integration/core/services/test_action_dispatch_logic.py`
- [✓] `tests/integration/core/services/test_action_executor_integration.py`
- [✓] `tests/integration/core/services/test_container_wiring.py`
- [✓] `tests/integration/core/services/test_create_overwrite_integration.py`
- [✓] `tests/integration/core/services/test_enhanced_validation_integration.py`
- [✓] `tests/integration/core/services/test_execution_orchestrator.py`
- [✓] `tests/integration/core/services/test_flexible_resource_parsing.py`
- [✓] `tests/integration/core/services/test_lazy_loading_integration.py`
- [✓] `tests/integration/core/services/test_partial_execution_integration.py`
- [✓] `tests/integration/core/services/test_plan_validator_integration.py`
- [✓] `tests/integration/core/services/test_reference_files_integration.py`
- [✓] `tests/integration/core/services/test_report_formats_integration.py`
- [✓] `tests/integration/core/services/test_report_whitespace_sanitization.py`
- [✓] `tests/integration/core/services/test_research_parsing_integration.py`
- [✓] `tests/integration/core/services/test_resilient_edit_matching_integration.py`
- [✓] `tests/integration/core/services/test_session_orchestration_integration.py`
- [✓] `tests/integration/core/services/test_session_orchestrator_validation.py`
- [✓] `tests/integration/core/services/test_session_resume.py`
- [✓] `tests/integration/core/services/test_session_service.py`
- [✓] `tests/integration/core/services/test_session_validation_integration.py`
- [✓] `tests/integration/core/services/test_validation_diagnostics_integration.py`

#### Implementation Notes (Scenario 3)
Refactored the entire integration suite (96 tests) to utilize the formal Test Harness Triad and `TestEnvironment` setup. Migrated ad-hoc mocking to the standardized `container` fixture and global mocks (e.g., `mock_fs`, `mock_shell`). Consolidated all `conftest.py` logic into `tests/suites/conftest.py` and removed the redundant global `tests/conftest.py`. Fixed a critical regression in `test_shell_adapter.py` related to parallel execution and resolved various linting/typing issues in the harness infrastructure. Resolved a subtle regression in session management caused by a `TypeError` in `PlanningService` (mock cost) and an isolation leak in `InitService` (path resolution), ensuring a stable foundation for Milestones 10+.

## 3. Architectural Changes
This slice implements the "Primary Driving Adapter" pattern for the test suite.

- **Migration:** Moving ad-hoc utilities to the `tests` boundary defined in Slice 09-01.
- **Pattern:** Transitioning from "String-Based Setup" to "Builder-Based Setup" for all plan-related inputs.
- **Dependency:** The `MarkdownPlanBuilder` becomes a first-class tool used by both tests and (potentially) internal diagnostic scripts.

## 4. Interaction Sequence
1.  **Test Case:** Requests the `container` fixture to get a fresh DI environment.
2.  **Test Case:** Uses `MarkdownPlanBuilder` to chain actions (e.g., `.add_create(...).add_execute(...)`).
3.  **Test Case:** Passes the `.build()` output to the `CliTestAdapter` or `IRunPlanUseCase`.
4.  **Test Case:** Asserts against the resulting `ExecutionReport` or CLI output.
