# Bug: Persistent OpenRouter Metadata "???"

- **Status:** Unresolved
- **Milestone:** 00
- **Vertical Slice:** [docs/project/slices/03-resilient-openrouter-metadata.md](/docs/project/slices/03-resilient-openrouter-metadata.md)

## Symptoms
Expected: Context window and cost are displayed correctly (e.g., "23.2k / 1M tokens", "$0.01").
Actual: Both show "???" (e.g., "23.2k / ??? tokens", "$???").

Reproduction steps:
1. Run `teddy start` with an OpenRouter model (e.g., `openrouter/deepseek/deepseek-v4-flash`).
2. Observe telemetry in the TUI or Console.

## Context & Scope
### Regressing Delta
The bug persists after the implementation of Slice 03, which was specifically designed to fix this. It's likely a regression or an edge case not covered by the original implementation.

### Environmental Triggers
- Model: `openrouter/deepseek/deepseek-v4-flash`
- Connection: OpenRouter API

### Ruled Out
- API Connectivity (Pathfinder responds, so the LLM call succeeds).

## Diagnostic Analysis
### Causal Model
1. `PlanningService` displays telemetry using the **requested model ID** from configuration (e.g., `openrouter/deepseek/deepseek-v4-flash`).
2. If the LLM call succeeds (Deferred Hydration), `LiteLLMAdapter.get_completion_cost` is called to calculate cost.
3. If LiteLLM doesn't recognize the model, `get_completion_cost` triggers hydration using the **resolved model ID** found in the response object (e.g., `deepseek/deepseek-v4-flash-20260525`).
4. The hydration logic injects metadata into `litellm.model_cost` only for this **resolved ID**.
5. The original **requested ID** remains unhydrated in LiteLLM's internal registry.
6. On the next turn, `PlanningService` still uses the requested ID for telemetry. `get_context_window` and `supports_pricing` return 0/False because they only check for the exact requested ID in the registry.

### Discrepancies
- Turn 02 shows "???" despite Turn 01 succeeding. Conflict: Turn 01 success should have hydrated the registry. (Resolved: Hydration targeted the resolved versioned ID, not the requested ID used for display).

### Investigation History
1. Initial report. Observation: "???" persists for `deepseek-v4-flash`. Conclusion: Investigation needed.
2. MRE Verification. Observation: `get_completion_cost` successfully calculates cost but leaves requested ID registry key empty. Conclusion: Root cause confirmed as Registry Fragmentation.
3. Fix Proof. Observation: Broadcasting metadata to both requested and resolved IDs in `get_completion_cost` resolves telemetry blindness. Conclusion: Fix proven.

## Solution
### Root Cause
The `LiteLLMAdapter.get_completion_cost` method implemented "Deferred Hydration" which correctly caught cost calculation failures for unmapped models. However, it only hydrated the specific model ID returned in the completion response (the versioned ID). It failed to synchronize this metadata with the original model alias requested by the user, which TeDDy uses for UI telemetry.

### Proven Fix
Modified `get_completion_cost` to extract both the `resolved_id` (from response) and the `requested_id` (from config/current state). The hydration logic now "broadcasts" the fetched metadata to both keys in LiteLLM's `model_cost` registry.

### Preventative Measures
- **Systemic Broadcasting**: Ensure all hydration logic in the `LiteLLMAdapter` (both during completion retries and deferred cost calculation) uses the same candidate extraction and broadcasting logic.
- **Sentinel Awareness**: Audit telemetry display services to ensure they handle the `0` sentinel for unknown context windows gracefully (already implemented).
