# Bug: OpenRouter Hydration Failure Revisited

- **Status:** Resolved
- **Milestone:** 00
- **Vertical Slice:** [docs/project/slices/03-resilient-openrouter-metadata.md](/docs/project/slices/03-resilient-openrouter-metadata.md)
- **Specs:** N/A

## Symptoms
User receives `Error: This model isn't mapped yet. model=deepseek/deepseek-v4-flash-20260423, custom_llm_provider=openrouter` when using `openrouter/deepseek/deepseek-v4-flash` despite prior hydration fixes.

## Context & Scope
### Regressing Delta
The bug is a systemic gap in the hydration strategy implemented in Slice 03. The original fix wrapped `get_completion` in a try-catch for `NotFoundError`.

### Environmental Triggers
- Use of a "Day-0" OpenRouter model (like `openrouter/deepseek/deepseek-v4-flash`) that is unknown to LiteLLM's internal registry.
- The `litellm.completion` call *succeeds* natively (because the provider is generic OpenAI-compatible and accepts the string), returning a response with a versioned model ID (e.g., `deepseek/deepseek-v4-flash-20260423`).

### Ruled Out
- The hydration logic `OpenRouterMetadataHydrator` (it correctly strips suffixes and formats data).
- The `get_completion` retry block (it is never triggered because the completion itself does not fail).

## Diagnostic Analysis
### Causal Model
1. **Completion Success:** When `LiteLLMAdapter.get_completion()` is called with an unknown `openrouter/` model, LiteLLM successfully routes the request to OpenRouter without throwing an error, because the provider is generic.
2. **Response Mutation:** OpenRouter responds with a completion object where the `model` field contains the resolved internal version (e.g., `deepseek/deepseek-v4-flash-20260423`).
3. **Cost Calculation Failure:** `PlanningService` subsequently calls `LiteLLMAdapter.get_completion_cost(response)`. Inside this method, LiteLLM attempts to look up the versioned model ID in its local `model_cost` registry.
4. **Deferred Exception:** Because the `model_cost` registry is empty for this model and `get_completion` never failed (so `_handle_hydration_retry` was never executed), LiteLLM throws a generic `Exception("This model isn't mapped yet...")`. This exception bubbles up and crashes the application, appearing exactly like a hydration failure.

### Discrepancies
- Observation: The previous fix injected metadata into `litellm.model_cost` but it still fails. (Resolved: The previous fix *never executes* because `get_completion` doesn't throw an error for these models; the error is deferred to `get_completion_cost`).

### Investigation History
1. Read current hydration logic in `litellm_adapter` and `openrouter_hydrator`.
2. Created MRE simulating the exact sequence of `get_completion`.
3. Observation: MRE `get_completion` succeeded without throwing an error.
4. Hypothesis: The error is raised during streaming iteration. (False: `stream=True` also succeeded).
5. Hypothesis: The error is raised during telemetry or cost calculation after the completion.
6. Observation: MRE reproduced the exact `Exception: This model isn't mapped yet...` when `get_completion_cost(response)` was called.
7. Conclusion: The root cause is that unknown OpenRouter models fail during cost calculation, not during completion, completely bypassing the previous retry mechanism.

## Solution
[To be populated after zero-touch verification]
