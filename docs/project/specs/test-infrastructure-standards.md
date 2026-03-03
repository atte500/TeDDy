# Specification: Test Infrastructure Standards

## 1. Problem Statement
The current test suite suffers from:
1.  **Mocking Boilerplate:** Test files repetitively register common mocks (`IUserInteractor`, `IFileSystemManager`, etc.) into the DI container, leading to maintenance overhead and fragile tests.
2.  **Top-Heavy Pyramid:** Acceptance tests are verifying low-level validation logic (e.g., error messages for missing files or invalid syntax), slowing the suite and hindering isolation.

## 2. Proposed Solution: Centralized Mocking
Common ports will be provided as shared fixtures in `tests/conftest.py`. These fixtures will:
1.  Initialize a `MagicMock(spec=IPort)`.
2.  Automatically register the mock instance in the `container` provided by the base `container` fixture.
3.  Return the mock for specific setup within individual tests.

## 3. Proposed Solution: Pyramid Rebalancing
- **Acceptance Tests:** Focused on "Happy Path" user journeys and CLI behavior.
- **Unit Tests:** Cover all parsing edge cases and individual validation rule logic.
- **Integration Tests:** Cover service-level orchestration and adapter/port contracts.

## 4. Refactoring List
The following files must be updated to remove manual `container.register` calls and local `mocks` fixtures:
- `tests/unit/core/services/test_plan_validator.py`
- `tests/unit/core/services/test_action_factory.py`
- `tests/unit/core/services/test_execution_orchestrator.py`
- `tests/unit/core/services/test_context_service.py`
- `tests/unit/core/services/test_action_dispatcher.py`
- `tests/unit/adapters/outbound/test_console_interactor.py`
- `tests/integration/core/services/test_execution_orchestrator.py`
- `tests/integration/core/services/test_plan_validator_integration.py`
- `tests/integration/adapters/inbound/test_cli_adapter.py`
- `tests/integration/adapters/outbound/test_web_searcher_adapter.py`
- `tests/acceptance/test_generalized_clipboard_output.py`
- `tests/acceptance/test_quality_of_life_improvements.py`
- `tests/acceptance/test_cli_polish.py`
- `tests/acceptance/test_interactive_execution.py`
- `tests/acceptance/test_change_preview_feature.py`
