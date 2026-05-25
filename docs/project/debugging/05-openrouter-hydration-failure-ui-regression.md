# Bug: OpenRouter Hydration Failure & UI Regressions

- **Status:** Resolved
- **Milestone:** 00
- **Vertical Slice:** [docs/project/slices/03-resilient-openrouter-metadata.md](/docs/project/slices/03-resilient-openrouter-metadata.md)
- **Specs:** N/A

## Symptoms
1. **Hydration Failure**: User sees `Error: This model isn't mapped yet. model=deepseek/deepseek-v4-flash-20260423` despite Slice 03 implementation.
2. **Bootstrap Lag**: "Checking configurations..." does not appear instantly.
3. **Over-Broad Message**: "Checking configurations..." appears for `execute` and `context` commands.

## Context & Scope
### Regressing Delta
Recent changes in Slice 03 intended to optimize startup and provide resilient model hydration. The message `typer.echo("Checking configurations...")` was moved into the Typer `bootstrap()` callback.

### Environmental Triggers
- Use of "Day-0" OpenRouter models (e.g., DeepSeek V4) that resolve to internal versioned IDs.
- Commands like `teddy context` or `teddy execute` triggering the global callback.

### Ruled Out
- `__main__.py` eager imports. Import profiling confirms TeDDy internal initialization is under 40ms.

## Diagnostic Analysis
### Causal Model
1. **UI Feedback Scope**: The `bootstrap()` callback in Typer executes before *every* command (`start`, `execute`, `context`), causing "Checking configurations..." to appear inappropriately across all interactions.
2. **UI Feedback Lag**: Typer parses commands and python loads modules *before* `bootstrap()` executes. When run via `poetry run`, standard environment startup creates a perceived lag (~400ms) before the callback can print the message.
3. **Hydration Registry Key Miss**: When `LiteLLMAdapter._handle_hydration_retry` parses the error `model=deepseek/deepseek-v4-flash-20260423, custom_llm_provider=openrouter`, it extracts only `deepseek/deepseek-v4-flash-20260423`. It then injects this raw ID into `litellm.model_cost`. However, LiteLLM's internal registry lookup requires the `openrouter/` prefix when resolving custom provider models. Because the prefix is omitted during injection, LiteLLM suffers a cache miss upon retry, and the `NotFoundError` bubbles up.

### Discrepancies
- Message not instant. (Resolved: Delay is standard Python/Poetry startup, not TeDDy logic. Can't be optimized, but message placement can be improved).
- Message appears on `execute`/`context`. (Resolved: `bootstrap` runs universally. The message must be localized to `start` where checking configuration is actually relevant).
- Hydration fails despite registry injection. (Resolved: Extracted model ID is missing the `openrouter/` prefix required by LiteLLM's internal registry lookup).

### Investigation History
1. Initial report: Hydration failing for DeepSeek V4; UI lag and visibility issues.
2. Profiled imports: Confirmed TeDDy imports take <40ms. Lag is standard Python/Poetry overhead.
3. Traced `__main__.py`: Confirmed `bootstrap` callback causes universal message visibility.
4. Traced `LiteLLMAdapter`: Identified that extracted versioned ID lacks `openrouter/` prefix when injected into `model_cost`, causing retry miss.

## Solution
1. **Hydration Mapping**: Modified `LiteLLMAdapter._handle_hydration_retry` to inject the fetched metadata under *all* candidate IDs (including the original requested alias like `openrouter/deepseek/deepseek-v4-flash`), rather than just the extracted versioned ID. This ensures LiteLLM's internal registry lookup succeeds immediately upon retry.
2. **Localized UI Feedback**: Moved `typer.echo("Checking configurations...")` out of the global Typer `bootstrap()` callback and directly into the `start` command. This eliminates the "visual lie" and scope creep on commands like `execute` and `context` that do not perform configuration checks. Performance profiling confirmed that these commands execute rapidly (<50ms internally) and the perceived lag was strictly psychological overhead from standard Python startup combined with the misplaced message.
