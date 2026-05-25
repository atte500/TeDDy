# Bug: OpenRouter DeepSeek Routing Error

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

When running `teddy start` with the model configured as `openrouter/deepseek/deepseek-v4-flash`, the LLM completion fails with:
`Error: LLM Completion failed: litellm.NotFoundError: GeminiException - `

Expected behavior: The LLM should complete successfully using the specified OpenRouter model.

## Context & Scope

### Regressing Delta
TBD - Need to check recent changes to `LiteLLMAdapter` or configuration handling.

### Environmental Triggers
- Model: `openrouter/deepseek/deepseek-v4-flash`
- Provider: OpenRouter (via LiteLLM)
- API Key: Provided (validated format `sk-or-...`)

### Ruled Out
TBD

## Diagnostic Analysis

### Causal Model
1. User configures `openrouter/deepseek/deepseek-v4-flash` in their local config.
2. The baseline `config.yaml` contains `custom_llm_provider: "gemini"`.
3. `LiteLLMAdapter.get_completion` retrieves the `llm` configuration block. Due to configuration layering in `YamlConfigAdapter` (recursive deep merge), the `custom_llm_provider: "gemini"` from the baseline persists if the user only overrides the `model` and `api_key`.
4. `LiteLLMAdapter` calls `litellm.completion(model="openrouter/...", custom_llm_provider="gemini", ...)`.
5. LiteLLM's internal routing prioritizes the `custom_llm_provider` parameter over any provider prefix in the `model` string. It attempts to route the OpenRouter model through the Gemini provider.
6. The Gemini provider fails to find the model and raises `litellm.NotFoundError: GeminiException`.

### Root Cause
The presence of a hardcoded `custom_llm_provider` in the baseline configuration creates a "sticky" default that interferes with LiteLLM's automatic provider detection. This is exacerbated by the `YamlConfigAdapter`'s deep-merge strategy, which preserves this metadata key even when the primary `model` key is overridden.

### Merge Logic Analysis
- **Current Behavior:** Recursive deep merge with a "Migration Shim" for flat overrides.
- **Pros:** Allows fine-grained overrides of nested blocks.
- **Cons:**
    1. **Semantic Leakage:** Stale metadata (like `custom_llm_provider`) persists when peers (like `model`) change.
    2. **Shim Inconsistency:** The Migration Shim (which allows root-level keys like `model` to override `llm.model`) only works for scalar lookups. Block lookups (e.g., `get_setting("llm")`) return the merged baseline block, which does NOT reflect the shim's override. This causes `LiteLLMAdapter` to see the baseline model even if the user tried to override it using the flat pattern.
- **Assessment:** The merge logic and the shim are both contributors to configuration fragility.

### Systemic Debt
1. **Redundant Baseline Defaults:** Including optional, provider-specific fields like `custom_llm_provider` in the baseline config creates "sticky" defaults that conflict with LiteLLM's auto-routing.
2. **Split-Brain Configuration:** The `YamlConfigAdapter` migration shim only applies to scalar lookups (`get_setting("a.b")`). Block lookups (`get_setting("a")`) return the merged dictionary *before* shim application. Since `LiteLLMAdapter` uses block lookups to pass `**kwargs` to LiteLLM, it frequently operates on stale or inconsistent data.
3. **Merge Persistence:** The deep merge logic has no mechanism to delete keys from the baseline, making it impossible for users to "unset" a baseline default without code changes.

## Solution

### Root Cause
A redundant `custom_llm_provider: "gemini"` in the baseline configuration leaks into the `llm` block passed to LiteLLM. Due to a flaw in the `YamlConfigAdapter`'s merge and shim logic, this metadata persists and takes precedence over model-string prefixes, causing LiteLLM to misroute requests.

### Proven Fix
1. **Baseline Migration:**
    - Change `llm.model` to `"openrouter/deepseek/deepseek-v4-flash"`.
    - Remove `custom_llm_provider: "gemini"`.
2. **Logic Repair:** Refactor `YamlConfigAdapter` to apply the migration shim to the internal configuration dictionary immediately after loading/merging. This ensures that block lookups (`get_setting("llm")`) are consistent with scalar lookups (`get_setting("llm.model")`).
3. **Merge Enhancement:** Update `_merge_dicts` to prune keys set to `null` (None) in the override, allowing users to explicitly unset baseline defaults.

### Discrepancies
- `DeepSeek` model results in `GeminiException`. Conflict: Why is Gemini involved in a DeepSeek/OpenRouter request? (resolved: Baseline `config.yaml` hardcodes `custom_llm_provider: "gemini"`, which leaks into the LiteLLM call due to deep-merge logic in `YamlConfigAdapter`. LiteLLM's `custom_llm_provider` parameter overrides the provider prefix in the model string.)

### Investigation History
1. Initial report received. `GeminiException` noted in `NotFoundError`.
2. Verified baseline `config.yaml` contains `custom_llm_provider: "gemini"`.
3. Verified `YamlConfigAdapter` uses a recursive `_merge_dicts` which preserves the baseline provider if not explicitly overridden by the user.
4. Created MRE `spikes/debug/02-openrouter-mre.py` and confirmed that passing `custom_llm_provider="gemini"` with an `openrouter/` model triggers the `GeminiException`.

## Solution
TBD
