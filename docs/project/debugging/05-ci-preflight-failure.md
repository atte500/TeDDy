# Bug: CI Preflight Configuration Failure

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-02-session-config-preflight](../slices/00-02-session-config-preflight.md)

## Symptoms
In CI (specifically Windows), `test_session_orchestrator_validation.py` fails with a `ConfigurationError`.
- **Expected:** Tests pass by either mocking the preflight check or providing valid config.
- **Actual:** `PlanningService.generate_plan` triggers `_run_preflight_check`, which finds the default placeholder key and raises `ConfigurationError`.

## Context & Scope
### Regressing Delta
The integration of `self._run_preflight_check()` in `PlanningService.generate_plan` (commit `b935e1ec`).

### Environmental Triggers
- Manifests in CI (Ubuntu/macOS/Windows).
- Likely masked locally if the developer has `OPENAI_API_KEY` or similar set in their shell, which `LiteLLMAdapter.validate_config` might detect.

### Ruled Out
- `IConfigService.get_config_path` (seems to work correctly as the path is reported).

## Diagnostic Analysis
### Causal Model
1. A validation failure occurs during `SessionOrchestrator.execute`.
2. The orchestrator triggers a replan via `SessionReplanner`.
3. `SessionReplanner` calls `PlanningService.generate_plan`.
4. `PlanningService.generate_plan` calls `_run_preflight_check`.
5. `_run_preflight_check` calls `llm_client.validate_config()`.
6. **Fault:** Instead of using the mock `ILlmClient` registered by `TestEnvironment`, `PlanningService` is using a real `LiteLLMAdapter`.
7. This happens because `PlanningService` depends on the `PlanningPorts` DTO. If `PlanningPorts` was resolved by the container *before* the mock was registered, or if it was registered as a singleton/instance with the real adapters, the mock `ILlmClient` is ignored.
8. **Root Cause:** In `infrastructure.py`, `ILlmClient` is registered without a scope, making it a **Singleton**. Once resolved (often during orchestrator setup), it cannot be overridden by `TestEnvironment.mock_port` because `punq` returns the cached instance.
9. The real `LiteLLMAdapter` finds the default "your-api-key" in the bundled config and returns an error.
10. `PlanningService` raises `ConfigurationError`, crashing the test.

### Discrepancies
- **Tests pass locally but fail in CI.** (Resolved: Local `.teddy/config.yaml` has a valid-looking key, masking the check. CI uses bundled default with placeholder.)
- **Real LiteLLMAdapter used in Integration Tests.** The `ConfigurationError` message proves `LiteLLMAdapter.validate_config` is running instead of a mock.

### Investigation History
1. CI Log Analysis. Found `ConfigurationError` in `test_session_orchestrator_validation.py`.
2. Local Env Check. Confirmed no `API_KEY` or `TOKEN` env vars are set locally.
3. Local Test Run. Confirmed tests pass locally because of a valid key in `.teddy/config.yaml`.
4. Reproduction. Neutralized local config and reproduced `ConfigurationError` locally in integration tests.
5. Code Audit. Found `ILlmClient` registered as a singleton in `infrastructure.py`.
6. Fix. Changed `ILlmClient` scope to `transient` in `infrastructure.py`.
7. Verification. Confirmed diagnostic and integration tests pass locally even with neutralized config.

## Solution
### Implemented Fixes
- Modified `src/teddy_executor/registries/infrastructure.py` to change `ILlmClient` registration scope from singleton to `punq.Scope.transient`.
- Updated `tests/suites/integration/core/services/test_session_orchestrator_validation.py` to explicitly mock `ILlmClient` in tests that trigger the preflight check.

### Prevention
- The `TestEnvironment` (Harness) now successfully overrides `ILlmClient` with a mock that returns an empty list for `validate_config()` by default.
- Ensuring all infrastructure ports are transient prevents "singleton caching" where real adapters leak into test containers.
