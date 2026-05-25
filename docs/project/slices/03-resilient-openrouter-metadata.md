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
- **Caching**: The OpenRouter catalog should be fetched at most once per session to minimize latency.
- **No Suffix Match**: If stripping the suffix (e.g. `-20260423`) still yields no match in the live catalog, fallback to "???".
- **Malformed Response**: Handle non-JSON or invalid schema responses from OpenRouter gracefully.

## Deliverables
- [ ] **Contract** - Define `IOpenRouterHydrator` port (internal to adapter layer).
- [ ] **Harness** - Add mock OpenRouter `/models` response to the test environment.
- [ ] **Logic** - Implement `OpenRouterMetadataHydrator` service that performs the fetch, suffix-stripping, and matching.
- [ ] **Logic** - Update `LiteLLMAdapter` to catch `NotFoundError` and trigger hydration.
- [ ] **Logic** - Update `LiteLLMAdapter.get_context_window()` to return a sentinel/0 when metadata is estimated.
- [ ] **Wiring** - Update the `container.py` to wire the hydrator into the adapter.
- [ ] **Refactor** - Update TUI/Console components to display "???" when the context window is unknown.
- [ ] **Showcase** - Create `spikes/showcase/03-openrouter-resilience.py` demonstrating the fix with a versioned model name.

## Implementation Plan
1. **Hydrator Service**: Create a small, focused service that fetches the OpenRouter catalog and provides a `get_metadata(model_id)` method with suffix-stripping logic.
2. **Adapter Integration**: Update `LiteLLMAdapter` to use this hydrator. Crucially, it should use `litellm.model_cost[key] = { ... }` to inject the data as proven in the Pathfinder's discovery.
3. **UI Updates**: Ensure that the `get_context_window` port returns a value that signals "Unknown" to the UI layers.
