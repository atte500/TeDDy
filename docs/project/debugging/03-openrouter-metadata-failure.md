# Bug: OpenRouter Metadata Failure & Startup Lag

- **Status:** Resolved
- **Milestone:** 00
- **Vertical Slice:** [docs/project/slices/03-resilient-openrouter-metadata.md](/docs/project/slices/03-resilient-openrouter-metadata.md)
- **Specs:** N/A

## Symptoms
- **Model Error**: `Error: This model isn't mapped yet. model=deepseek/deepseek-v4-flash-20260423, custom_llm_provider=openrouter.` even when configured with `openrouter/deepseek/deepseek-v4-flash`.
- **Startup Lag**: Significant delay between `teddy start` and `Checking configurations...`.
- **LiteLLM Warnings**: Warnings about missing `botocore` for Bedrock/SageMaker.

## Context & Scope
### Regressing Delta
Recent implementation of Slice 03 (OpenRouter Metadata Hydrator) which was intended to fix this issue.

### Environmental Triggers
- Use of OpenRouter with versioned model names (e.g., DeepSeek).
- Lack of `botocore` in the environment.

### Ruled Out
- N/A

## Diagnostic Analysis
### Causal Model
1. **Startup Lag (Lag 1):** The CLI `bootstrap()` callback eagerly executes `_run_cli_preflight_check`, which triggers a blocking `import litellm` (~2.2s) and a blocking remote connectivity check via `check_valid_key` (~2.2s). This adds ~4.4s of latency to every CLI command, regardless of whether it uses the LLM.
2. **LiteLLM Warnings:** During `import litellm`, the library attempts to pre-load event-stream shapes for Bedrock/SageMaker. If `botocore` is missing, it emits noisy warnings to `stderr`.
3. **OpenRouter Failure:** When calling OpenRouter, LiteLLM resolves requested IDs (e.g., `openrouter/deepseek/deepseek-v4-flash`) to internal versioned IDs (e.g., `deepseek/deepseek-v4-flash-20260423`).
4. **Hydration Mismatch:** The existing hydration logic only injected metadata for the *requested* ID. Because LiteLLM retries using the *resolved* versioned ID, it fails again with `NotFoundError` as that specific key remains unmapped in its internal registry.

### Discrepancies
- The error message shows `model=deepseek/deepseek-v4-flash-20260423` (no `openrouter/` prefix). (Resolved: LiteLLM resolves OpenRouter models to internal IDs that may omit the provider prefix and include version suffixes. Hydrating both the requested and the actual model ID fixes the retry loop.)
- Significant lag before "Checking configurations...". (Resolved: This is the combined weight of Python interpreter, Typer, and package imports. Actual blocking lag starts with `_run_cli_preflight_check`.)

### Investigation History
1. Initial report. User still seeing error despite Slice 03 completion.
2. Shadow Test Verification. Confirmed that parsing the error message for the actual model ID and hydrating all variants (requested, actual, no-provider) successfully resolves the `NotFoundError`.
3. Profiling Startup. Identified that `validate_config(include_remote=True)` is the primary bottleneck (~4.4s).
4. Silence Verification. Confirmed that setting LiteLLM logger to `CRITICAL` before import silences `botocore` warnings.

## Solution
1. **Hydration Fix:** Update `LiteLLMAdapter` to parse the `NotFoundError` message for the actual model ID and hydrate all name variants.
2. **Startup Optimization:** Move the remote connectivity check out of the global `bootstrap()` path. It should only be performed lazily by `PlanningService` or similar LLM-consuming components.
3. **Warning Suppression:** Ensure LiteLLM logging is silenced at the highest level during adapter initialization to prevent `botocore` noise.
