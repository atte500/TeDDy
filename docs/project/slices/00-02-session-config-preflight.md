# Slice: Session Configuration Preflight Check
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](../specs/interactive-session-workflow.md)

## Business Goal
As a user, I want the system to validate my API keys and model configuration before attempting to generate a plan, so that I receive immediate, actionable feedback on how to fix my configuration if it is missing or invalid.

## Scenarios
> As a user with an unconfigured system (placeholder API key), I want to be told exactly where to find my config file when I start a session.
```gherkin
Given a configuration file at ".teddy/config.yaml" containing "llm.api_key: 'your-api-key'" # pragma: allowlist secret
When I start a session with "teddy resume my-session"
Then the system should not call the LLM
And the system should display a message: "Configuration Error: 'llm.api_key' is still set to the default placeholder."
And the system should display the path to the config file: ".teddy/config.yaml"
And the session turn should halt.
```

> As a user with a missing required key for a specific provider, I want the system to identify the missing environment variable.
```gherkin
Given a configuration file with "llm.model: 'gemini/gemini-pro'"
And "GOOGLE_API_KEY" is not set in the environment
And "llm.api_key" is not set in the config
When I start a session
Then the system should display a message: "Missing required environment variable or config: GOOGLE_API_KEY (or GEMINI_API_KEY)"
And the session turn should halt.
```

## Deliverables
- [x] **Contract** - Add `get_config_path() -> str` to `IConfigService`.
- [x] **Logic** - Implement `get_config_path()` in `YamlConfigAdapter`.
- [x] **Contract** - Add `validate_config() -> list[str]` to `ILlmClient`.
- [x] **Logic** - Implement `validate_config()` in `LiteLLMAdapter` (env check + placeholder rejection).
- [x] **Wiring** - Integrate preflight gate into `PlanningService.generate_plan`.
- [ ] **Logic** - Update `LiteLLMAdapter.validate_config` to satisfy env-var checks if `api_key` is in config.
- [ ] **Wiring** - Add preflight gate to `handle_new_session` before user prompt.
- [ ] **Wiring** - Add preflight gate to `handle_resume_session` and `handle_plan_generation`.

## Delta Analysis
- `src/teddy_executor/core/ports/outbound/config_service.py`: Interface change.
- `src/teddy_executor/adapters/outbound/yaml_config_adapter.py`: Implementation of path exposure.
- `src/teddy_executor/core/ports/outbound/llm_client.py`: Interface change.
- `src/teddy_executor/adapters/outbound/litellm_adapter.py`: Implementation of preflight logic.
- `src/teddy_executor/core/services/planning_service.py`: Integration of the preflight gate.

## Guidelines for Implementation
- Use TDD: Start by creating a test in `tests/suites/unit/core/services/test_planning_service_preflight.py` that mocks `llm.validate_config()` returning errors.
- In `LiteLLMAdapter`, `validate_environment` checks `os.environ`. If the key is provided in the `llm` config block instead, you may need to temporarily patch `os.environ` or manually verify the keys against the `missing_keys` returned by LiteLLM.
- The placeholder check for `"your-api-key"` should be case-insensitive.

## Implementation Notes
### Deliverable: Contract - Add get_config_path() -> str to IConfigService
- Added `get_config_path` to `IConfigService` port.
- Implemented `get_config_path` in `YamlConfigAdapter` to return the `_config_path` attribute.
- Verified via unit tests in `tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py`.

### Deliverable: Contract - Add validate_config() -> list[str] to ILlmClient
- Added `validate_config` abstract method to `ILlmClient` interface.
- Added a stub implementation to `LiteLLMAdapter` to maintain global test suite integrity during the transition.
- Created contract enforcement test in `tests/suites/unit/core/ports/outbound/test_llm_client_contract.py`.

### Deliverable: Logic - Implement validate_config() in LiteLLMAdapter
- Implemented `validate_config` in `LiteLLMAdapter`.
- Added case-insensitive check for the `"your-api-key"` placeholder.
- Integrated `litellm.validate_environment(model)` to detect missing provider-specific environment variables or config keys.
- Verified behavior via dedicated unit tests in `tests/suites/unit/adapters/outbound/test_litellm_adapter_preflight.py`.

### Deliverable: Wiring - Integrate preflight gate into PlanningService.generate_plan
- Added `ConfigurationError` to `src/teddy_executor/core/domain/models/exceptions.py`.
- Injected preflight check at the start of `PlanningService.generate_plan`.
- Optimized the test harness (`TestEnvironment`) by centralizing happy-path mock defaults in `mock_port`. This prevents regressions where truthy `MagicMock` returns would trigger the error branch in tests.
- Verified system-wide stability with a 100% pass rate (681 tests).
