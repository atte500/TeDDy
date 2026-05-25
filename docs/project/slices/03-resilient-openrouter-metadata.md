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
- **API Timeout**: If the OpenRouter metadata fetch takes > 2 seconds, it must timeout and fallback to "???" to avoid hanging the CLI.
- **Remote Config Timeout**: If the LLM remote connectivity check takes > 2 seconds, it must timeout to prevent blocking CLI startup.
- **Caching**: The OpenRouter catalog should be fetched at most once per session to minimize latency.
- **No Suffix Match**: If stripping the suffix (e.g. `-20240525`) still yields no match in the live catalog, fallback to "???".
- **Malformed Response**: Handle non-JSON or invalid schema responses from OpenRouter gracefully.

## Deliverables
- [x] **Contract** - Define `IOpenRouterHydrator` port (internal to adapter layer).
- [x] **Harness** - Add mock OpenRouter `/models` response to the test environment.
- [x] **Logic** - Implement `OpenRouterMetadataHydrator` service that performs the fetch, suffix-stripping, and matching.
- [x] **Logic** - Update `LiteLLMAdapter` to catch `NotFoundError` and trigger hydration.
- [x] **Logic** - Update `LiteLLMAdapter.get_context_window()` to return a sentinel/0 when metadata is estimated.
- [x] **Wiring** - Update the `container.py` to wire the hydrator into the adapter.
- [x] **Refactor** - Update TUI/Console components to display "???" when context window or session cost is unknown.
- [x] **Showcase** - Create `spikes/showcase/03-openrouter-resilience.py` demonstrating the fix with a versioned model name.
- [ ] **Logic** - Refine `LiteLLMAdapter` hydration to parse actual model IDs from error messages.
- [ ] **Logic** - Silence LiteLLM logging at the critical level during initialization to suppress `botocore` warnings.
- [ ] **Refactor** - Move `validate_config(include_remote=True)` from the global `bootstrap()` path to a lazy, on-demand check in `PlanningService`.
- [ ] **Logic** - Add a 2s timeout to all remote configuration and connectivity checks.

## Implementation Plan
1. **Hydrator Service**: Create a small, focused service that fetches the OpenRouter catalog and provides a `get_metadata(model_id)` method with suffix-stripping logic.
2. **Adapter Integration**: Update `LiteLLMAdapter` to use this hydrator. Crucially, it should use `litellm.model_cost[key] = { ... }` to inject the data as proven in the Pathfinder's discovery.
3. **UI Updates**: Ensure that the `get_context_window` port returns a value that signals "Unknown" to the UI layers.
4. **Resilient Hydration**: Update `LiteLLMAdapter._handle_hydration_retry` to parse the `NotFoundError` string for the `model=...` value. This ensures that even if LiteLLM resolves to a versioned ID (e.g., `-20260423`), the metadata is injected into the correct registry key.
5. **Startup Optimization**:
    - Move the `include_remote=True` check out of `_run_cli_preflight_check`.
    - Update `PlanningService._run_preflight_check` to perform the remote check only when a generation is actually requested.
    - Set `os.environ["LITELLM_LOG"] = "CRITICAL"` and configure the LiteLLM logger to `CRITICAL` during adapter initialization to suppress `botocore` noise.
    - Implement a 2s timeout for `litellm.check_valid_key` calls.

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
