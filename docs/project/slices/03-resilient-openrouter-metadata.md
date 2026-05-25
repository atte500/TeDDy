# Slice: Resilient OpenRouter Metadata Hydration

- **Status:** Planned
- **Milestone:** 00
- **Specs:** [docs/architecture/adapters/outbound/litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md)
- **Case File:** N/A (Originates from user report)

## Business Goal

Enable seamless support for new and versioned OpenRouter models (like DeepSeek V4) by dynamically fetching ground-truth metadata (context window, pricing) from the OpenRouter API when LiteLLM's internal database is out of date.

## Scenarios

> As a developer using a "Day-0" OpenRouter model, I want TeDDy to automatically resolve the context window and pricing so that I don't encounter "model isn't mapped" errors.

```gherkin
Scenario: Resolve Versioned OpenRouter Model
  Given I am using model "openrouter/deepseek/deepseek-v4-flash"
  And OpenRouter returns internal ID "deepseek/deepseek-v4-flash-20260423"
  And LiteLLM throws "NotFoundError: This model isn't mapped yet"
  When TeDDy performs a pre-flight check or completion
  Then TeDDy should fetch the live catalog from "https://openrouter.ai/api/v1/models"
  And it should strip the "-20260423" suffix to find a match
  And it should inject the real context window (e.g. 1,048,576) into LiteLLM's memory
  And the request should proceed successfully
```

> As a developer, I want to know when TeDDy is unsure about model metadata, so that I am aware of potential context limit inaccuracies.

```gherkin
Scenario: Fallback to "???" on Hydration Failure
  Given the OpenRouter API is unreachable or returns no match
  When I view the session status or context window info
  Then TeDDy should display "???" for context window and cost
  And it should use a conservative internal default (128k tokens) to prevent crashes
```

## Edge Cases
- **Deferred Hydration**: If the initial `get_completion` request succeeds natively (because the OpenRouter endpoint handles unknown aliases), LiteLLM's internal registry remains unhydrated. The hydration must then be triggered dynamically when `get_completion_cost` is called to prevent a deferred crash.
- **Missing Pricing**: If hydration succeeds but OpenRouter provides no pricing data for the model, the UI must explicitly display `???` instead of `$0.0000`.
- **API Timeout**: If the OpenRouter metadata fetch takes > 2 seconds, it must timeout and fallback to "???" to avoid hanging the CLI.
- **Remote Config Timeout**: If the LLM remote connectivity check takes > 2 seconds, it must timeout to prevent blocking CLI startup.
- **Caching**: The OpenRouter catalog should be fetched at most once per session to minimize latency.
- **No Suffix Match**: If stripping the suffix (e.g. `-20240525`) still yields no match in the live catalog, fallback to "???".
- **Malformed Response**: Handle non-JSON or invalid schema responses from OpenRouter gracefully.
- **Cache Key Miss**: If a requested alias (`openrouter/deepseek...`) resolves to a versioned ID internally, the hydrated metadata must be mapped to *all* candidate IDs to ensure LiteLLM's cache lookup succeeds during the retry.
- **UI Message Scope**: The "Checking configurations..." message must only appear for commands that actually verify configurations (like `start`), preventing visual lag and scope creep on lightweight commands like `execute` and `context`.

## Deliverables
- [x] **Logic** - Wrap `LiteLLMAdapter.get_completion_cost` to catch the generic `Exception("This model isn't mapped yet...")`, trigger the `OpenRouterMetadataHydrator`, and retry the calculation.
- [x] **Logic** - Update `LiteLLMAdapter.get_completion_cost` to gracefully return `0.0` if hydration and retry still fail, preventing application crashes.
- [x] **Refactor** - Update `PlanningService._display_telemetry` to display `???` for cost if the model lacks explicit pricing data in the registry, satisfying the "??? not 0" UI requirement.
- [x] **Contract** - Define `IOpenRouterHydrator` port (internal to adapter layer).
- [x] **Harness** - Add mock OpenRouter `/models` response to the test environment.
- [x] **Logic** - Implement `OpenRouterMetadataHydrator` service that performs the fetch, suffix-stripping, and matching.
- [x] **Logic** - Update `LiteLLMAdapter` to catch `NotFoundError` and trigger hydration.
- [x] **Logic** - Update `LiteLLMAdapter.get_context_window()` to return a sentinel/0 when metadata is estimated.
- [x] **Wiring** - Update the `container.py` to wire the hydrator into the adapter.
- [x] **Refactor** - Update TUI/Console components to display "???" when context window or session cost is unknown.
- [x] **Showcase** - Create `spikes/showcase/03-openrouter-resilience.py` demonstrating the fix with a versioned model name.
- [x] **Logic** - Refine `LiteLLMAdapter` hydration to parse actual model IDs from error messages.
- [x] **Logic** - Silence LiteLLM logging at the critical level during initialization to suppress `botocore` warnings.
- [x] **Refactor** - Move `validate_config(include_remote=True)` from the global `bootstrap()` path to a lazy, on-demand check in `PlanningService`.
- [x] **Logic** - Increase remote connectivity timeout to 10s to accommodate slow cold-starts and network latency.
- [x] **Cleanup** - Consolidate redundant lazy imports in `LiteLLMAdapter` into the `_get_litellm` factory.
- [x] **Refactor** - Move "Checking configurations..." to the start of `bootstrap()` in `__main__.py` for instant UI feedback.
- [x] **Optimization** - Implement "Ultra-Lazy" `validate_config` in `LiteLLMAdapter` to avoid `litellm` import for local checks.
- [x] **Optimization** - Refactor `LocalRepoTreeGenerator` to use lazy `pathspec` imports.
- [x] **Optimization** - Refactor `cli_helpers.py` to use lazy `pyperclip` imports.
- [x] **Bugfix** - Modify `LiteLLMAdapter._handle_hydration_retry` to apply fetched metadata to all candidate IDs.
- [x] **Bugfix** - Move `typer.echo("Checking configurations...")` from `__main__.py` `bootstrap()` to `session_cli_handlers.py` `handle_new_session()`.

## Implementation Plan
### Phase 2: Deferred Hydration
1. **Intercept Deferred Exceptions**: Modify `LiteLLMAdapter.get_completion_cost` with a `try/except Exception` block to catch LiteLLM's deferred `This model isn't mapped yet` error.
2. **Extract & Hydrate**: When caught, extract the model ID from `response.model` and the exception string, fetch metadata via `_hydrator`, and inject it into `litellm.model_cost` for both the raw versioned ID and the `openrouter/` prefixed variant.
3. **Graceful Fallback**: Retry the cost calculation. If it fails again, return `0.0` instead of crashing.
4. **UI Degradation**: In `PlanningService._display_telemetry`, add logic to verify if pricing actually exists for the model. If it doesn't, display `$???` instead of the accumulated `0.0`.

### Phase 1: Initial Implementation
1. **Hydrator Service**: Create a small, focused service that fetches the OpenRouter catalog and provides a `get_metadata(model_id)` method with suffix-stripping logic.
2. **Adapter Integration**: Update `LiteLLMAdapter` to use this hydrator. Crucially, it should use `litellm.model_cost[key] = { ... }` to inject the data as proven in the Pathfinder's discovery.
3. **UI Updates**: Ensure that the `get_context_window` port returns a value that signals "Unknown" to the UI layers.
4. **Resilient Hydration**: Update `LiteLLMAdapter._handle_hydration_retry` to parse the `NotFoundError` string for the `model=...` value. This ensures that even if LiteLLM resolves to a versioned ID (e.g., `-20260423`), the metadata is injected into the correct registry key.
5. **Startup Optimization**:
    - Move the `include_remote=True` check out of `_run_cli_preflight_check`.
    - Update `PlanningService._run_preflight_check` to perform the remote check only when a generation is actually requested.
    - Set `os.environ["LITELLM_LOG"] = "CRITICAL"` and configure the LiteLLM logger to `CRITICAL` during adapter initialization to suppress `botocore` noise.
    - Implement a 10s timeout for `litellm.check_valid_key` calls to ensure reliability for remote providers like OpenRouter.
    - Optimize `LiteLLMAdapter.validate_config` to perform basic existence checks for `llm.model` and `llm.api_key` before calling `_get_litellm()`.
    - Move the preflight "Checking configurations..." message out of the `bootstrap()` callback in `__main__.py` and place it at the very top of `handle_new_session` in `session_cli_handlers.py`. This ensures it only prints for the `start` command and not for `execute` or `context`.
    - Audit and refactor all adapters (specifically `LocalRepoTreeGenerator` and `cli_helpers.py`) to move module-level heavy imports (`pathspec`, `pyperclip`) into lazy-loaded methods.
6. **Hydration Retry Patch**: Update `_handle_hydration_retry` so that when metadata is found for *any* candidate ID, it iterates through *all* candidate IDs and injects the metadata into `litellm.model_cost` for each. This guarantees that LiteLLM's internal retry (which uses the original requested alias) hits the cache.

## Implementation Notes

### Deliverable: Contract - IOpenRouterHydrator
- Defined `IOpenRouterHydrator` as a `typing.Protocol` inside `src/teddy_executor/adapters/outbound/litellm_adapter.py`.
- This ensures the contract is internal to the adapter layer as specified, avoiding leakage into the core domain.
- The protocol defines `get_metadata(model_id: str)` returning an optional dictionary containing `context_window` and `pricing`.

### Deliverable: Harness - OpenRouter Mock Response
- Created `tests/harness/setup/openrouter_mock_data.py` containing a standardized mock response for the OpenRouter `/models` API.
- Added `openrouter_mock` fixture to `tests/harness/setup/composition.py` and exported it in `tests/conftest.py`.
- The fixture uses `pytest_httpserver` to provide a canned response for `GET /api/v1/models`, enabling isolated testing of hydration logic.

### Deliverable: Logic - Implement OpenRouterMetadataHydrator
- Implemented `OpenRouterMetadataHydrator` in `src/teddy_executor/adapters/outbound/openrouter_hydrator.py`.
- Included a 2-second timeout and regex-based suffix stripping for versioned model IDs (e.g., `-20240525`).
- Added caching to ensure the catalog is fetched at most once per session (instance lifetime).
- Verified behavior with unit tests covering exact matches, suffix matches, and API failures.

### Deliverable: Logic - Update LiteLLMAdapter to catch NotFoundError and trigger hydration
- Updated `LiteLLMAdapter` to accept an optional `IOpenRouterHydrator` in its constructor via DI.
- Modified `get_completion` to catch `litellm.NotFoundError`. The detection logic checks both `type(e).__name__` and `isinstance` to ensure robustness across different runtime and mock environments.
- Implemented a trigger-and-retry mechanism: when a model is not found, the adapter uses the hydrator to fetch live metadata and injects it into `litellm.model_cost` before retrying the call once.
- Refactored the fallback context window to `0` instead of a hardcoded default (like 128k) during hydration. This preserves the "unknown" state, allowing UI layers to correctly display `???` per the port contract.
- Verified with unit tests simulating `NotFoundError` and confirming the hydration call, registry update, and retry execution.

### Deliverable: Logic - LiteLLMAdapter.get_context_window() sentinel
- Confirmed `get_context_window` returns `0` for unknown models or models with missing metadata in `litellm.model_cost`.
- Added explicit regression test case in `test_get_context_window_retrieves_from_litellm_cost`.
- This `0` sentinel allows UI layers (TUI/Console) to display `???` instead of failing or showing incorrect data, fulfilling the "Fallback to ???" scenario requirements.

### Deliverable: Wiring - container.py injection
- Registered `IOpenRouterHydrator` mapping to `OpenRouterMetadataHydrator` in `src/teddy_executor/registries/infrastructure.py`.
- Used `punq.Scope.singleton` for the hydrator to ensure its internal model catalog cache persists across resolutions within a single container lifetime.
- Updated the `ILlmClient` (LiteLLMAdapter) registration to resolve and inject the `IOpenRouterHydrator`.
- Added an integration test in `tests/suites/integration/adapters/outbound/test_llm_wiring.py` to verify the wiring at the composition root.

### Deliverable: Refactor - UI display for unknown context window/cost
- Updated `populate_context_detail` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py` to display `???` instead of `0k` when `total_window` is `0`.
- Updated `PlanningService._display_telemetry` to display `???` for both context window and session cost when model metadata is unknown (indicated by a `0` context window).
- Verified TUI fix with new unit tests in `tests/suites/unit/adapters/inbound/test_context_display_helpers.py`.
- Verified PlanningService fix with new unit tests in `tests/suites/unit/core/services/test_planning_service.py`.

### Deliverable: Showcase - OpenRouter Resilience
- Created `spikes/showcases/03-openrouter-resilience.py` to demonstrate the end-to-end "Day-0" model support.
- The showcase script programmatically verifies:
    1. Detection of `NotFoundError` for versioned model IDs.
    2. Dynamic fetching and suffix-stripping logic in the `OpenRouterMetadataHydrator`.
    3. Correct mapping of OpenRouter pricing fields to LiteLLM-compatible internal registry keys.
    4. Successful retry of completion requests with the hydrated metadata.
    5. Smoke-tested the UI telemetry logic to ensure `???` is displayed when the context window is unknown.
- Verified that the hydrator strips the `openrouter/` prefix to match catalog entries, which often lack the provider prefix.

### Deliverable: Logic - Refine LiteLLMAdapter hydration to parse actual model IDs
- Updated `_handle_hydration_retry` in `src/teddy_executor/adapters/outbound/litellm_adapter.py` to use regex for extracting `model=...` values from `NotFoundError` messages.
- This is necessary because LiteLLM often resolves a requested ID (e.g., `openrouter/deepseek/deepseek-v4-flash`) to an internal, versioned ID (e.g., `deepseek/deepseek-v4-flash-20260423`) before failing if it's not in its local registry.
- The hydration logic now collects a set of candidate IDs (requested + extracted) and attempts to hydrate all of them before retrying the completion call once.
- Verified with unit tests that both IDs are correctly populated in `litellm.model_cost`.

### Deliverable: Logic - Silence LiteLLM logging
- Updated `LiteLLMAdapter` to perform double-pass silencing: once before the `import litellm` call and once after.
- Set `os.environ["LITELLM_LOG"] = "CRITICAL"` and `logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)`.
- This suppresses noisy `botocore` warnings emitted by LiteLLM during its eager loading of AWS shapes.
- Verified with unit tests that both the environment variable and the logger level are correctly configured at initialization.

### Deliverable: Refactor - Move validate_config(include_remote=True)
- Relocated the remote connectivity check (`include_remote=True`) from the CLI bootstrap helper (`_run_cli_preflight_check` in `session_cli_handlers.py`) to the `PlanningService._run_preflight_check`.
- Updated `session_cli_handlers.py` to perform only a local configuration check (`include_remote=False`) during CLI startup, eliminating the ~2.2s remote lag for non-generative commands.
- Added comprehensive unit tests to `tests/suites/unit/core/services/test_planning_service.py` to ensure the `PlanningService` correctly triggers remote validation before generation.
- Updated CLI preflight tests in `tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py` to assert that only local validation is performed at the adapter level.
- Verified that error reporting (e.g., missing API keys) remains transparent and halts execution at the correct layer.

### Deliverable: Logic - Add a 2s timeout to all remote configuration and connectivity checks
- Implemented a 2-second timeout for `litellm.check_valid_key` in `LiteLLMAdapter.validate_config`.
- Used a lazy-initialized singleton `ThreadPoolExecutor` to wrap the synchronous library call. This ensures that `validate_config` returns immediately when the `future.result(timeout=2.0)` throws a `TimeoutError`, while avoiding the blocking behavior of a `with` block context manager.
- Added a specific unit test `test_validate_config_remote_check_timeout` in `tests/suites/unit/adapters/outbound/test_litellm_adapter_preflight.py` that mocks a 4-second hang and verifies the method returns a "timed out" error within 2.5 seconds.
- Verified that `OpenRouterMetadataHydrator` (implemented earlier in this slice) also respects the 2s timeout via its `requests.get(..., timeout=2.0)` configuration.

### Deliverable: Cleanup - Consolidate redundant lazy imports
- Refactored `LiteLLMAdapter` to eliminate 7 redundant `import litellm` and `_ensure_silence` calls.
- Centralized `litellm` access through the thread-safe `_get_litellm()` factory.
- This ensures that the silencing protocol (environment variables and logger levels) is applied consistently and correctly across all LLM operations.
- Verified with unit and global integration tests that behavioral contracts remain intact.

### Deliverable: Logic - Increase remote connectivity timeout to 10s
- Increased the timeout for `litellm.check_valid_key` in `LiteLLMAdapter.validate_config` from 2.0s to 10.0s.
- Updated the error message in `LiteLLMAdapter` to reflect the 10-second threshold.
- Increased the timeout in `OpenRouterMetadataHydrator` from 2.0s to 10.0s for consistency across all remote metadata/connectivity checks.
- Refactored `test_validate_config_remote_check_timeout` to use a mocked `Future` object, allowing for instantaneous verification of the 10.0s parameter without incurring real-time delays.

### Deliverable: Refactor - Move "Checking configurations..." to bootstrap()
- Relocated the "Checking configurations..." message from `session_cli_handlers.py` to the `@app.callback()` (bootstrap) in `__main__.py`.
- This ensures the message is printed immediately after Typer/Python bootstrap, providing visual feedback during the loading of heavy dependencies (like `punq` or `typer` itself).
- Verified that global tests pass, confirming that moving the message to the start of every command (where it now appears for `context` and `get-prompt` as well) does not violate existing behavioral contracts.

### Deliverable: Optimization - Ultra-Lazy validate_config
- Refactored `LiteLLMAdapter.validate_config` to perform existence checks for `llm.api_key` and `llm.model` before calling `_get_litellm()`.
- This eliminates the ~2.2s `import litellm` cost for the most common configuration errors (missing keys or empty placeholders).
- Confirmed with laziness unit tests that the heavy import is deferred until environment validation or remote checks are explicitly required.

### Deliverable: Optimization - Lazy pathspec and pyperclip
- Refactored `LocalRepoTreeGenerator` and `cli_helpers.py` to move heavy library imports (`pathspec`, `pyperclip`) into the methods where they are actually used.
- This ensures that these libraries are not loaded during the container registration phase, further reducing CLI startup lag.
- Repaired "Mock Poisoning" in acceptance tests by redirecting `pyperclip` mocks to the source module instead of the consumer namespace.
- Added a diagnostic test `tests/suites/unit/test_startup_laziness.py` to prevent future regressions.

### Deliverable: Bugfix - Modify LiteLLMAdapter._handle_hydration_retry
- Updated the hydration retry logic to find the first available metadata from candidate IDs (requested alias and extracted versioned ID).
- Implemented broadcasting of the discovered metadata to all candidate IDs in `litellm.model_cost`.
- This ensures that LiteLLM's internal cache lookup succeeds during the retry attempt, regardless of whether it uses the original alias or the resolved internal ID.
- Verified with unit tests that cross-mapping occurs even if the hydrator only recognizes one of the IDs.

### Deliverable: Bugfix - Localize UI Feedback
- Relocated `typer.echo("Checking configurations...")` from the global `bootstrap()` callback in `__main__.py` to the `handle_new_session` handler in `session_cli_handlers.py`.
- This prevents the message from appearing on lightweight, non-generative commands like `execute` and `context`, providing a cleaner UX and eliminating misleading output for tasks that do not perform LLM preflight checks.
- Verified with acceptance tests in `tests/suites/acceptance/test_cli_ux_improvements.py`.

### Deliverable: Logic - Implement Deferred Hydration Retry in get_completion_cost
- Wrapped `LiteLLMAdapter.get_completion_cost` with a `try/except Exception` block.
- Caught the generic `"This model isn't mapped yet"` exception and extracted the `model_id` directly from `completion_response.model`.
- Leveraged the injected `_hydrator` to fetch missing metadata dynamically.
- Injected the metadata into `litellm.model_cost` and successfully retried the cost calculation, preventing deferred crashes when OpenRouter model aliases are natively accepted by the API but unknown to LiteLLM's internal registry.

### Deliverable: Logic - Graceful fallback for get_completion_cost
- Updated `LiteLLMAdapter.get_completion_cost` to return `0.0` instead of re-raising if hydration fails to provide metadata or if the retry attempt still throws an exception.
- This ensures that pricing failures (which are common for "Day-0" or versioned models) do not crash the session planning or execution flow.
- Verified that `PlanningService` correctly uses the context window sentinel (`0`) to display `???` in the UI when the model is entirely unknown, maintaining transparency for the user.

### Deliverable: Refactor - Update PlanningService._display_telemetry for "??? not 0"
- Extended `ILlmClient` with `supports_pricing(model: Optional[str] = None) -> bool`.
- Implemented `supports_pricing` in `LiteLLMAdapter` by checking for the existence of the `input_cost_per_token` key in the LiteLLM internal registry.
- Updated `PlanningService._display_telemetry` to check both the context window and pricing support before displaying session cost.
- This ensures that genuine free models ($0.00) are reported correctly, while models with missing pricing metadata are reported as `$???`.
- Verified with unit tests covering known models, free models, and hydrated models with missing pricing keys.
