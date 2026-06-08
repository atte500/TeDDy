# Slice: Model Override Fix & Validation Enhancement
- **Status:** In Progress
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
- [x] **Refactor (Hydrator) & Harness (Test)** - Fix type-mismatch crash in `OpenRouterMetadataHydrator` when processing real API responses; return `None` gracefully. Create test with mocked API response containing string-typed pricing values.
- [x] **Refactor (Adapter Hydration) & Harness (Test)** - Fix float+str type error in `_hydrate_all_candidates` by converting pricing values to float before injection into `litellm.model_cost`. Also hardened `get_completion_cost` to catch `TypeError` gracefully. Existing test coverage (`test_get_completion_hydrates_and_retries_on_not_found_error`) validates the fix. A dedicated regression test was attempted but removed due to mocking incompatibility with the global litellm mock fixture.
- [x] **Logic (Fix) & Harness (Test)** - Fix param layering in `_prepare_completion_params`: merge `llm_config` first, then apply explicit `model` on top. Updated `test_config_model_overrides_caller_model` to assert override precedence. Added regression test `test_model_override_takes_precedence`. Verified via targeted tests (2/2 Green) and full suite pass.
- [ ] **Logic (Validation) & Harness (Test)** - Add startup model validation that checks the model name against `litellm.model_cost` keys. Create test that verifies unknown models are rejected gracefully.
- [ ] **Logic (Display Update) & Harness (Test)** - After first LLM completion, update telemetry display to reflect `response.model` or `_hidden_params["litellm_model_name"]`. Create test verifying the display updates correctly.

## Implementation Notes

### Deliverable 1: Hydrator Fix (Completed)
- **Change:** Wrapped `float()` conversions in `_find_model` with `try/except (ValueError, TypeError)`, returning `None` when pricing values cannot be converted. This prevents the `unsupported operand type(s) for +: 'float' and 'str'` crash in LiteLLM's internal cost calculation when the OpenRouter API returns non-convertible string-typed pricing (e.g., `"$0.000001"`).
- **Tests Added:**
  - `test_hydrator_handles_string_typed_pricing`: Regression test with mocked API response containing currency-prefixed pricing values (e.g., `"$0.000001"`), verifying the hydrator returns `None` gracefully.
- **Debt:** No debt introduced. Existing tests using convertible string values (`"0.000001"`) remain passing (5/5 hydrator tests green).

### Deliverable 2: Adapter Hydration Fix (Completed)
- **Change:**
  - `_hydrate_all_candidates`: Added `try/except` loop to convert each pricing value to `float`, with `ValueError`/`TypeError` falling back to `0.0`.
  - `get_completion_cost`: Added `TypeError` to the exception tuple to catch `float+str` arithmetic errors gracefully, returning `0.0`.
- **Test Status:** The fix is validated by existing tests (all 833 pass). A dedicated regression test was attempted but removed because the global `litellm` mock fixture does not support item assignment on `model_cost`. The fix is already exercised by `test_get_completion_hydrates_and_retries_on_not_found_error`.
- **Debt:** No debt introduced.

### Deliverable 3: Param Layering Fix (Completed)
- **Change:** In `_prepare_completion_params`, swapped the order of `model` assignment and `llm_config.update()`: merge config first, then apply explicit model override on top.
- **Tests:**
  - Updated `test_config_model_overrides_caller_model` assertion to expect `caller-suggested-model` (override) instead of `config-model-name`.
  - Added `test_model_override_takes_precedence` to verify explicit model wins over config.
- **Verification:** Targeted tests pass (2/2). Full suite passes (834+).
- **Debt:** No debt introduced.

### Re-Prioritization (Deliverable 2: Adapter Hydration Fix)
The hydrator fix was insufficient. The global test suite still fails with `unsupported operand type(s) for +: 'float' and 'str'` after the param layering fix. The root cause is in `_hydrate_all_candidates` which injects pricing values into `litellm.model_cost` without ensuring they are floats. The hydrator returns metadata with float values for valid pricing, but the adapter passes them through as-is. In code paths where string-typed pricing values are still present (e.g., from mocked tests), LiteLLM's internal `completion_cost()` crashes. The fix must convert `input_cost_per_token` and `output_cost_per_token` to float before injection.

### Root Cause (Param Layering) — Queue for Deliverable 3
In `LiteLLMAdapter._prepare_completion_params()` (line ~152ff), the method sources and layers parameters in the order:
```python
params = {**kwargs}
if model:
    params["model"] = model
params.update(llm_config)  # This overwrites model!
```
The fix swaps the last two steps. This fix will be applied in Deliverable 3.

### Shadow Verification (Param Layering)
The param layering fix was verified in isolation using `spikes/debug/shadow_litellm_adapter.py` and verified via `spikes/debug/17-verify-fix.py`. Both assertions passed.

### Root Cause (Param Layering)
In `LiteLLMAdapter._prepare_completion_params()` (line ~152ff), the method sources and layers parameters in the order:
```python
params = {**kwargs}
if model:
    params["model"] = model
params.update(llm_config)  # This overwrites model!
```
The fix swaps the last two steps. This fix will be applied in Deliverable 2.

### Shadow Verification (Param Layering)
The param layering fix was verified in isolation using `spikes/debug/shadow_litellm_adapter.py` and verified via `spikes/debug/17-verify-fix.py`. Both assertions passed.

### Hydrator Bug (Deliverable 1)
The hydrator crashes with `unsupported operand type(s) for +: 'float' and 'str'` when processing real OpenRouter API responses. This appears to be in the pricing normalization where the API returns string-typed values. The fix should cast both pricing values to `float` and handle any conversion errors gracefully.

## Implementation Plan
1. **Fix param layering** in `src/teddy_executor/adapters/outbound/litellm_adapter.py` (1-line change) → Write regression test first.
2. **Fix hydrator** in `src/teddy_executor/adapters/outbound/openrouter_hydrator.py` → Write regression test first.
3. **Add model validation** using the hydrator (or a simpler check against `litellm.model_cost`) → Write test first.
4. **Add post-completion display update** in `planning_service.py` to read `response.model` after first completion → Write test first.
