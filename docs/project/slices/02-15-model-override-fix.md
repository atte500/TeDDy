# Slice: Model Override Fix & Validation Enhancement
- **Status:** Draft
- **Type:** Bugfix
- **Milestone:** [Milestone 2: Stability & Polish](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** N/A (ad-hoc bug fix)
- **Prototype:** [Case File 17: Invalid Model Metadata](/docs/project/debugging/17-invalid-model-metadata.md)
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md)

## Business Goal
When a user specifies a `--model` override via CLI (`teddy start --model <custom_model>`), that override must actually take effect for LLM API calls. The system should display correct context window and cost metadata for known models, gracefully handle unknown models, and validate model names at startup.

## Scenarios

> As a user, I want to override the LLM model via `--model` flag on `teddy start` and have that model actually used for API calls, so that I can test different models without modifying `config.yaml`.

```gherkin
Given a session has been started with `--model openrouter/openai/gpt-4o`
And the config.yaml contains `llm.model: openrouter/deepseek/deepseek-v4-flash:nitro`
When the first LLM completion is made
Then the actual API call should use `openrouter/openai/gpt-4o`
And the telemetry display should show the correct model metadata
```

> As a user, I want to provide an invalid model name and receive a clear error message at startup, rather than having the system silently fall back to the config model.

```gherkin
Given a session is started with `--model openrouter/this-model-does-not-exist`
When the startup validation runs
Then the system should display an error: "Model 'openrouter/this-model-does-not-exist' not found in OpenRouter catalog."
And the session should not be created
```

> As a user, I want the telemetry display to reflect the actual model that served my request after the first completion, even if the provider performed a fallback.

```gherkin
Given a session is using a valid model
When the first LLM completion returns with `response.model` = "deepseek/deepseek-v4-flash-20260423"
Then the telemetry display should update to show "deepseek/deepseek-v4-flash-20260423"
And the context window and cost should reflect the actual serving model
```

## Edge Cases
- **No override provided**: When `--model` is not specified, the config model should be used as before (backward compatibility).
- **Empty model string**: If `--model` is an empty string, it should be ignored and the config model used.
- **Resume with override**: `teddy resume --model <different_model>` should update the session's model for subsequent turns.
- **Hydrator API failure**: If the hydrator's HTTP request to OpenRouter fails, the system should gracefully fall back to existing `litellm.model_cost` data without crashing.
- **Provider fallback**: If OpenRouter maps an invalid model to a real one, the display should update to show the real model after the first completion.

## Deliverables
- [ ] **Logic (Fix)** - `LiteLLMAdapter._prepare_completion_params`: Swap the order of merging so that `llm_config` is merged first, then the explicit `model` parameter is applied on top. [Verified via shadow file.]
- [ ] **Harness (Test)** - Create regression test `test_model_override_takes_precedence` in `tests/suites/unit/adapters/outbound/test_litellm_adapter.py` that verifies `_prepare_completion_params` prioritizes explicit model over config model.
- [ ] **Logic (Validation)** - Add startup model validation: before session creation, check the model name against the OpenRouter model list (or known `litellm.model_cost` keys). If unknown, display a clear error and abort session creation.
- [ ] **Harness (Test)** - Create integration test for model validation that mocks the OpenRouter API to return a known model list, and verifies unknown models are rejected.
- [ ] **Logic (Display Update)** - After the first LLM completion in a turn, update the telemetry display to reflect `response.model` (or `_hidden_params["litellm_model_name"]`) so the user sees the actual serving model.
- [ ] **Harness (Test)** - Create test that verifies telemetry display is updated after first completion with the correct model from response.
- [ ] **Refactor (Hydrator)** - Fix the type-mismatch crash in `OpenRouterMetadataHydrator._find_model` or `get_metadata` when processing real API responses. Ensure it returns `None` gracefully instead of crashing.
- [ ] **Harness (Test)** - Create test for hydrator with mocked OpenRouter API response that contains string-typed pricing values, verifying it returns `None` (or metadata) without crashing.

## Implementation Notes

### Root Cause
In `LiteLLMAdapter._prepare_completion_params()` (line ~152ff), the method sources and layers parameters in the order:
```python
params = {**kwargs}
if model:
    params["model"] = model
params.update(llm_config)  # This overwrites model!
```
The fix swaps the last two steps.

### Shadow Verification
The fix was verified in isolation using `spikes/debug/shadow_litellm_adapter.py` and verified via `spikes/debug/17-verify-fix.py`. Both assertions passed: override model takes precedence when provided; config model is used as fallback when no override is given.

### Hydrator Bug
The hydrator crashes with `unsupported operand type(s) for +: 'float' and 'str'` when processing real OpenRouter API responses. This appears to be in the pricing normalization where the API returns string-typed values. The fix should cast both pricing values to `float` and handle any conversion errors gracefully.

## Implementation Plan
1. **Fix param layering** in `src/teddy_executor/adapters/outbound/litellm_adapter.py` (1-line change) → Write regression test first.
2. **Fix hydrator** in `src/teddy_executor/adapters/outbound/openrouter_hydrator.py` → Write regression test first.
3. **Add model validation** using the hydrator (or a simpler check against `litellm.model_cost`) → Write test first.
4. **Add post-completion display update** in `planning_service.py` to read `response.model` after first completion → Write test first.
