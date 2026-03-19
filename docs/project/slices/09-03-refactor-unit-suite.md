# Slice 09-03: Refactor Unit Suite
- **Status:** Planned
- **Milestone:** [Milestone 09: Hexagonal Test Architecture](../milestones/09-hexagonal-test-architecture.md)
- **Specs:** N/A

## 1. Business Goal
Extend the benefits of the Test Harness Triad (Setup, Driver, Observer) to the unit test suite. This will eliminate setup rot, replace brittle string-based assertions with typed DTOs, and bring all unit test files into compliance with the project's mandatory 300 SLOC limit.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Refactor SLOC Offenders (Services) [✓]
**Goal:** Migrate the largest service unit tests to the harness and bring them under the 300-line limit.
- **Precondition:** Several service unit tests exceed 300 SLOC due to manual Markdown string setup.
- **Success Condition:** `tests/suites/unit/core/services/test_parser_advanced_actions.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_formatter_action_logs.py` uses `ReportParser` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_validator_edit.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_parser_errors.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_parser_metadata.py` uses `MarkdownPlanBuilder` and is < 300 SLOC.
- **Success Condition:** `tests/suites/unit/core/services/test_execution_orchestrator.py` uses `TestEnvironment` and is < 300 SLOC.
#### Deliverables
- [✓] Refactor `tests/suites/unit/core/services/test_parser_advanced_actions.py` using `MarkdownPlanBuilder`.
- [✓] Refactor `tests/suites/unit/core/services/test_formatter_action_logs.py` using `ReportParser`.
- [✓] Refactor `tests/suites/unit/core/services/test_validator_edit.py` using `MarkdownPlanBuilder`.
- [✓] Refactor `tests/suites/unit/core/services/test_parser_errors.py` using `MarkdownPlanBuilder`.
- [✓] Refactor `tests/suites/unit/core/services/test_parser_metadata.py` using `MarkdownPlanBuilder`.
- [✓] Refactor `tests/suites/unit/core/services/test_execution_orchestrator.py` using `TestEnvironment`.

**Implementation Notes:**
- Verified SLOC for all target service unit tests; all are well under the 300-line limit.
- Corrected `DEFAULT_SIMILARITY_THRESHOLD` to 0.95 in `Plan` domain model to match project specifications.
- Restored `Validation Errors` and `Plan AST` diagnostic sections in execution reports by fixing data flow in `SessionOrchestrator` and `SessionReplanner`.

### Scenario 2: Standardize Unit Setup Patterns [▶]
**Goal:** Ensure all remaining unit tests utilize the `TestEnvironment` (Setup) for DI isolation.
- **Precondition:** Unit tests use a mix of manual mocking and ad-hoc setup.
- **Success Condition:** All unit tests in `tests/suites/unit/` use the `container` or `env` fixture for dependency management.
#### Deliverables
- [ ] Audit and refactor remaining unit test files to use the `container` or `env` fixture:
  - [ ] `tests/suites/unit/adapters/inbound/test_cli_formatter.py`
  - [ ] `tests/suites/unit/adapters/inbound/test_reviewer_app.py`
  - [ ] `tests/suites/unit/adapters/inbound/test_textual_plan_reviewer.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_console_interactor.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_litellm_adapter.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_litellm_adapter_robustness.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_shell_adapter_background.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_shell_adapter_granular_failure.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_shell_adapter_timeout.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_shell_adapter_windows_logic.py`
  - [ ] `tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py`
  - [ ] `tests/suites/unit/core/domain/models/test_execution_report.py`
  - [ ] `tests/suites/unit/core/domain/models/test_models.py`
  - [ ] `tests/suites/unit/core/domain/models/test_project_context.py`
  - [ ] `tests/suites/unit/core/domain/models/test_web_search_results.py`
  - [ ] `tests/suites/unit/core/domain/test_models.py`
  - [ ] `tests/suites/unit/core/ports/inbound/test_plan_parser_errors.py`
  - [ ] `tests/suites/unit/core/services/test_action_dispatcher.py`
  - [ ] `tests/suites/unit/core/services/test_action_dispatcher_normalization.py`
  - [ ] `tests/suites/unit/core/services/test_action_factory.py`
  - [ ] `tests/suites/unit/core/services/test_action_factory_timeout.py`
  - [ ] `tests/suites/unit/core/services/test_context_aware_validation.py`
  - [ ] `tests/suites/unit/core/services/test_context_service.py`
  - [ ] `tests/suites/unit/core/services/test_edit_matcher_resilience.py`
  - [ ] `tests/suites/unit/core/services/test_edit_simulator.py`
  - [ ] `tests/suites/unit/core/services/test_edit_simulator_bulk.py`
  - [ ] `tests/suites/unit/core/services/test_edit_simulator_fuzzy.py`
  - [ ] `tests/suites/unit/core/services/test_formatter_misc.py`
  - [ ] `tests/suites/unit/core/services/test_init_service.py`
  - [ ] `tests/suites/unit/core/services/test_markdown_report_formatter_enhancements.py`
  - [ ] `tests/suites/unit/core/services/test_orchestrator_data_flow.py`
  - [ ] `tests/suites/unit/core/services/test_orchestrator_isolation.py`
  - [ ] `tests/suites/unit/core/services/test_parser_basic_actions.py`
  - [ ] `tests/suites/unit/core/services/test_parser_create_overwrite.py`
  - [ ] `tests/suites/unit/core/services/test_parser_edit_bulk.py`
  - [ ] `tests/suites/unit/core/services/test_parser_formatting.py`
  - [ ] `tests/suites/unit/core/services/test_parser_infrastructure.py`
  - [ ] `tests/suites/unit/core/services/test_parser_misc.py`
  - [ ] `tests/suites/unit/core/services/test_planning_service.py`
  - [ ] `tests/suites/unit/core/services/test_planning_service_logging.py`
  - [ ] `tests/suites/unit/core/services/test_report_content_preservation.py`
  - [ ] `tests/suites/unit/core/services/test_report_crash_repro.py`
  - [ ] `tests/suites/unit/core/services/test_resource_alias_unit.py`
  - [ ] `tests/suites/unit/core/services/test_session_orchestrator.py`
  - [ ] `tests/suites/unit/core/services/test_session_orchestrator_initial_prompt.py`
  - [ ] `tests/suites/unit/core/services/test_session_orchestrator_resume.py`
  - [ ] `tests/suites/unit/core/services/test_session_orchestrator_validation.py`
  - [ ] `tests/suites/unit/core/services/test_session_service.py`
  - [ ] `tests/suites/unit/core/services/test_session_service_context.py`
  - [ ] `tests/suites/unit/core/services/test_session_service_cost.py`
  - [ ] `tests/suites/unit/core/services/test_session_service_robustness.py`
  - [ ] `tests/suites/unit/core/services/test_session_service_state.py`
  - [ ] `tests/suites/unit/core/services/test_session_service_transition.py`
  - [ ] [ ] `tests/suites/unit/core/services/test_validator_create.py`
  - [ ] `tests/suites/unit/core/services/test_validator_create_overwrite.py`
  - [ ] `tests/suites/unit/core/services/test_validator_edit_performance.py`
  - [ ] `tests/suites/unit/core/services/test_validator_edit_resilience.py`
  - [ ] `tests/suites/unit/core/services/test_validator_execute.py`
  - [ ] `tests/suites/unit/core/services/test_validator_misc.py`
  - [ ] `tests/suites/unit/core/services/test_validator_read.py`
  - [ ] `tests/suites/unit/core/test_report_parsing_helpers.py`
  - [ ] `tests/suites/unit/core/utils/test_markdown_utils.py`
  - [ ] `tests/suites/unit/core/utils/test_serialization.py`
  - [ ] `tests/suites/unit/test_cli_adapter.py`
  - [ ] `tests/suites/unit/test_environment_harness.py`
  - [ ] `tests/suites/unit/test_initial.py`
  - [ ] `tests/suites/unit/test_plan_builder.py`
  - [ ] `tests/suites/unit/test_report_parser.py`

## 3. Architectural Changes
This slice propagates the **Test Harness Triad** pattern from the high-level suites into the unit suite.

- **Driver Migration:** Unit tests for parsers (`IPlanParser`) and validators (`IPlanValidator`) will migrate from hardcoded Markdown strings to the `MarkdownPlanBuilder`. This ensures that unit-level testing remains synchronized with the official protocol format.
- **Observer Migration:** Unit tests for formatters (`IMarkdownReportFormatter`) will migrate from manual regex assertions to the `ReportParser`. This allows formatters to be tested against a structured DTO representation of their output.
- **Setup Migration:** All unit tests will standardize on the `container` fixture for Dependency Injection, ensuring that unit tests are truly isolated and that mocks are correctly injected into the subjects under test.
