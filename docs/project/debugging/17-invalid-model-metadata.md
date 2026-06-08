# Bug: Invalid Model Name Accepted with Unknown Context/Cost
- **Status:** Resolved
- **Milestone:** [Milestone 2: Stability & Polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [Slice 02-15: Model Override Fix & Validation Enhancement](/docs/project/slices/02-15-model-override-fix.md)
- **Specs:** N/A

## Symptoms
**Expected:** When using `teddy start --model openrouter/deepseek/deepseek-v4-proh:nitro`, the system should either reject the invalid model name with a clear error OR map it to a known model and display correct context window and cost.

**Actual:** The command succeeds, the model is used, but the telemetry display shows `???` for context tokens and `$???` for session cost. The model name `openrouter/deepseek/deepseek-v4-proh:nitro` is passed through to LiteLLM without validation.

**Minimal Reproduction Steps:**
1. Run `teddy start --model openrouter/deepseek/deepseek-v4-proh:nitro -m "test" -y`
2. Observe the session metadata line: `• Model: openrouter/deepseek/deepseek-v4-proh:nitro | Context: ??? / ??? tokens | Session Cost: $???`

## Context & Scope
### Regressing Delta
This appears to be an existing behavior, not a regression. The model name is passed directly to LiteLLM without validation against known model registries. The `LiteLLMAdapter.get_context_window()` and `supports_pricing()` methods check `litellm.model_cost` for the raw model string, which fails for unknown models. The `IOpenRouterHydrator` has fallback logic to fetch metadata from OpenRouter API, but it may fail if the model ID after suffix/prefix stripping is still invalid.

### Environmental Triggers
- Any model name not in LiteLLM's built-in registry (`litellm.model_cost`)
- Use of `teddy start --model <unknown-model>` or `teddy resume --model <unknown-model>`
- The `:nitro` suffix (or other OpenRouter routing shortcuts) causes stripping but the base model may still be valid or invalid.

### Ruled Out
- [Placeholder for ruled-out components after investigation]

## Diagnostic Analysis
### Causal Model
The telemetry display in `planning_service.py` (method `_display_telemetry`) calls `LiteLLMAdapter.get_context_window()` and `supports_pricing()`. These methods check `litellm.model_cost` for the exact model string. If the model is not in `litellm.model_cost`:
- `get_context_window()` returns 0 (using `model_info.get("max_input_tokens") or model_info.get("max_tokens") or 0`).
- `supports_pricing()` checks for `"input_cost_per_token"` key and returns False.

The `OpenRouterMetadataHydrator` is called as a fallback (pre-emptive hydration) but has two failure modes:
1. **API Response Bug**: The hydrator crashes with `unsupported operand type(s) for: 'float' and 'str'` when processing the real OpenRouter API response. This suggests a type mismatch in the `_find_model` method or in the response parsing (likely the `pricing` dict contains string values where floats are expected, or vice versa, and the `float(pricing.get("prompt", 0))` conversion succeeds but a string concatenation elsewhere fails).
2. **Invalid Model Lookup**: Even if the API call succeeds, if the stripped model ID (e.g., `deepseek/deepseek-v4-proh`) is not in the OpenRouter catalog, `get_metadata` returns None.

The CLI validation (`litellm.validate_environment`) does not reject invalid model names — it only checks for missing API keys or environment variables. For invalid models, it returns empty errors because LiteLLM trusts the user's model string and will attempt to use it.

**Fallback Behavior (Debunked)**: The probe with `openrouter/this-model-definitely-does-not-exist-12345` returned `deepseek/deepseek-v4-flash-20260423`. At first this appeared to be OpenRouter's fallback, but after the user changed the config model to `openrouter/deepseek/deepseek-v4-pro:nitro` and re-ran the probe, the response changed to `deepseek/deepseek-v4-pro-20260423`. This definitively proves **our code is the fallback**, not OpenRouter. The root cause is a parameter overwrite bug in `_prepare_completion_params`.

Thus the bug has three components:
1. **Parameter Overwrite Bug (Primary):** `_prepare_completion_params()` merges `llm_config` from config.yaml AFTER setting the explicitly passed `model` parameter, silently overwriting the CLI override with the config model.
2. **No Model Validation:** No step validates the model name at startup; it just accepts whatever is passed and silently uses the config model.
3. **Hydrator Crash (Secondary):** The hydrator crashes with a type-mismatch error when processing real OpenRouter API responses.

### Discrepancies
- The model `openrouter/deepseek/deepseek-v4-proh:nitro` is accepted by the CLI without validation, and the session starts successfully. This contradicts the expectation that an invalid model name should either be rejected or mapped to a known model with correct context/cost.
- The hydrator crashes with `unsupported operand type(s) for +: 'float' and 'str'` when making a real API request (discovered during probing). The hydrator should gracefully handle type mismatches or API response format changes. (Resolved: Identified as a separate bug in the hydrator's response processing.)

### Investigation History
1. MRE created and executed. Observation: get_context_window returns 0 and supports_pricing returns False for the invalid model (all scenarios). The hydrator fails to return metadata because the stripped model ID `deepseek/deepseek-v4-proh` is not in OpenRouter's catalog. Conclusion: The bug is in the model resolution pipeline — no validation of model existence before session creation, and no fallback that provides unknown metadata gracefully.
2. Validate config probe executed. Observation: `litellm.validate_environment` returns empty errors for both valid and invalid models (when include_remote=False). Conclusion: LiteLLM does not validate model existence against a registry; it trusts the model string and only checks API keys/env vars.
3. Hydrator real-request probe executed. Observation: The hydrator crashed with `unsupported operand type(s) for +: 'float' and 'str'` when making a live API call to OpenRouter. Conclusion: The hydrator has a type-mismatch bug in its response processing, likely in the pricing normalization where string values are returned from the API and float conversion fails or concatenation occurs. This is a secondary bug that makes the hydrator unreliable even for valid models.
4. **Decisive config-fallback probe (Turn 17).** User changed config model to `openrouter/deepseek/deepseek-v4-pro:nitro` then ran `--model` with completely invalid name `openrouter/this-is-completely-invalid-model-name-99999`. Observation: The response model was `deepseek/deepseek-v4-pro-20260423` — matching the config model, NOT the previous default. Conclusion: **Our code is falling back to the config model.** The root cause is in `_prepare_completion_params()` where `params.update(llm_config)` overwrites the explicitly passed model parameter.
5. **Shadow verification (Turn 21).** Created shadow file `spikes/debug/shadow_litellm_adapter.py` with fixed param layering (llm_config merged first, then model override applied on top). Verification probe `spikes/debug/17-verify-fix.py` tested `_prepare_completion_params` with explicit override `openrouter/openai/gpt-4o` against config model `openrouter/deepseek/deepseek-v4-pro:nitro` using a mocked config service. Two scenarios tested: (a) with explicit override → override model took precedence; (b) without override → config model was used as fallback. Both assertions passed. Conclusion: The param layering fix is empirically verified. No production code was touched; verification used shadow file only.

## Solution
### Root Cause
In `LiteLLMAdapter._prepare_completion_params()` (line ~152 of `litellm_adapter.py`), the method layers parameters in this order:
1. Start with `params = {**kwargs}`
2. If `model` is passed explicitly, set `params["model"] = model`
3. **Then merge `llm_config` from config.yaml on top**: `params.update(llm_config)`

Step 3 **silently overwrites** the passed `model` with the config model. This means `--model` on the CLI is completely ignored for actual API calls. The display reads from `meta.yaml` (which correctly stores the CLI override), but the API call uses the config model — causing the mismatch where the display shows `???` (invalid name) while a real model serves the request.

### The Fix (Verified via Shadow File)
The fix is a one-line change: in `_prepare_completion_params`, **merge `llm_config` FIRST**, then apply the explicit `model` parameter on top. This ensures CLI overrides take precedence.

```python
# Before (buggy):
params = {**kwargs}
if model:
    params["model"] = model
params.update(llm_config)

# After (fixed):
params = {**kwargs}
params.update(llm_config)  # Base config first
if model:
    params["model"] = model  # Override on top
```

### Preventative Measures
1. **Parameter Layering Convention:** All adapter methods should follow the convention of applying base config FIRST, then applying explicit overrides LAST. This prevents silent overwrites.
2. **Model Validation at Startup:** Fetch the OpenRouter model list (or use a cached registry) and validate the model name before creating a session. This would have caught the invalid name immediately.
3. **Post-Completion Display Update:** After the first LLM call, read `response.model` and update the display to reflect the actual serving model. This ensures telemetry accuracy even when the provider does its own fallback.
4. **Hydrator Hardening:** Fix the type-mismatch crash in `OpenRouterMetadataHydrator` to gracefully return None instead of crashing.
