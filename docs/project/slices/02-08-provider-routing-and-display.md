# Slice: 02-08 Provider Routing and Display

- **Status:** Cancelled
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:**
  - [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md)
  - [PlanningService](/docs/architecture/core/services/planning_service.md)
  - [PromptManager](/docs/architecture/core/services/prompt_manager.md)

## Business Goal

Display the actual downstream provider that served each LLM request in the CLI telemetry output, so the user knows which provider OpenRouter routed to (e.g., DeepSeek, Together, OpenAI).

## Scenarios

> As a user, I want the `• Model:` line in the CLI session output to include the resolved downstream provider so I can see which provider OpenRouter selected for each turn.
```gherkin
Given a running session
When the `planning_service._display_telemetry()` method is called after an LLM completion
Then the `• Model:` line shows `{model} | {resolved_provider}` where `resolved_provider` is extracted from `response._hidden_params["provider"]`
```

> As a user, I want the provider to be populated from the very first turn, not just subsequent ones.
```gherkin
Given a new session
When the first turn's plan is generated
Then the `• Model:` line includes `| {provider}` immediately (no delay)
```

> As a user, I no longer want the `llm.provider` config value to be special-cased in the LiteLLM adapter, since provider ordering is transparently handled by OpenRouter's routing.
```gherkin
Given a configuration with `llm.provider: anthropic`
When the adapter prepares completion parameters
Then no `provider` key is removed or specially handled in the params dict
And the `extra_body.providers.order` field is NOT set by adapter code (OpenRouter default routing applies)
```

> As a user, I want to see documentation of the `llm` config section pass-through behaviour and the `:nitro` / `:floor` shortcuts so I know how to configure and use them.
```gherkin
Given the component documentation
When I read the LiteLLMAdapter docs
Then I see documented: `llm` config section passes through to litellm params, and `:nitro` / `:floor` shortcut behaviours
```

## Edge Cases

- **Missing `_hidden_params`**: If the response object does not have `_hidden_params` (e.g., local models like Ollama), provider falls back to `"unknown"` and the Model line omits the `| unknown` suffix.
- **Missing `provider` key inside `_hidden_params`**: Same graceful fallback to `"unknown"`.
- **First-turn display**: Confirmed that `_display_telemetry` runs after `update_meta`; provider IS available from turn 1.
- **Removing special-casing**: The `llm.provider` config value was used only to set `extra_body.providers.order` for OpenRouter. Removal means OpenRouter uses its default routing; no functional regression expected.

## Deliverables

- [ ] **Contract** - Add provider extraction in `PromptManager.update_meta`: `meta["provider"] = str(getattr(response, "_hidden_params", {}).get("provider", "unknown"))`.
- [ ] **Contract** - Remove `llm.provider` special-casing in `LiteLLMAdapter._prepare_completion_params` (the `params.pop("provider", None)` and subsequent `extra_body` logic).
- [ ] **Harness** - Unit tests for `PromptManager.update_meta` provider extraction: mock a response with `_hidden_params["provider"] = "openai"`, verify meta dict gets `provider = "openai"`.
- [ ] **Harness** - Unit tests for `LiteLLMAdapter._prepare_completion_params` confirming no `llm.provider` handling occurs.
- [ ] **Harness** - Unit tests for `PlanningService._display_telemetry` showing `| {provider}` appended to Model line.
- [ ] **Logic** - Implement provider extraction in `prompt_manager.py`.
- [ ] **Logic** - Remove `llm.provider` special-casing in `litellm_adapter.py`.
- [ ] **Logic** - Append `| {provider}` to the `• Model:` line in `planning_service.py:_display_telemetry`.
- [ ] **Wiring** - Acceptance test verifying full CLI output includes `| {provider}` for the Model line in session mode.
- [ ] **Documentation** - Update `litellm_adapter.md` component doc: remove special-casing description, document `llm` config pass-through, document `:nitro`/`:floor` shortcuts.
- [ ] **Documentation** - Update `planning_service.md` component doc: document `_display_telemetry` metadata block and provider display.
- [ ] **Documentation** - Update `prompt_manager.md` component doc: document provider extraction from `_hidden_params`.
- [ ] **Cleanup** - Remove any stale references to `llm.provider` special-casing in config examples or comments.

## Implementation Notes

*(To be filled by Developer during implementation.)*

## Cancellation Rationale

This slice was cancelled after the Prototyper validated the core assumption against a real OpenRouter API call.

**The Assumption:** `response._hidden_params["provider"]` is populated by litellm with the downstream provider name (e.g., `"deepseek"`, `"together"`, `"openai"`).

**The Reality:** A real OpenRouter call to `openrouter/deepseek/deepseek-v4-flash:nitro` (with valid API key from `.teddy/config.yaml`) returned a response where `_hidden_params` contained **no `provider` key**. The available keys were: `custom_llm_provider`, `region_name`, `headers`, `additional_headers`, `optional_params`, `litellm_call_id`, `api_base`, `model_id`, `response_cost`, `litellm_model_name`, `_response_ms`, `callback_duration_ms`. The `custom_llm_provider` value was `"openrouter"` (the gateway, not the downstream server).

**Three alternative approaches were considered but rejected:**

| Path | Approach | Verdict |
|------|----------|---------|
| **A** | Use `custom_llm_provider` (shows `openrouter` as gateway) | Rejected — doesn't show downstream provider |
| **B** | Parse provider from resolved model name (e.g., `deepseek/...` → `deepseek`) | Rejected — fragile, depends on naming conventions |
| **C** | Separate API call to OpenRouter status endpoint | Rejected — adds latency and complexity, scope creep |

**Decision:** The feature is cancelled because the downstream provider data is not exposed by litellm for OpenRouter routes. Any implementation would either show the gateway (`openrouter`) rather than the downstream provider, or require a separate OpenRouter API integration that is beyond the scope of this slice.

**Prototype evidence:** The standalone prototype at [spikes/prototypes/02-08-provider-routing.py](/spikes/prototypes/02-08-provider-routing.py) contains the full diagnostic code and is preserved as documentation of the investigation.

## Implementation Plan

### Data Pipeline (Confirmed)

```
litellm.completion()
  → response._hidden_params["provider"] populated by litellm
  → prompt_manager.update_meta(meta, response)
      → meta["model"] from response.model (existing)
      → meta["provider"] from response._hidden_params["provider"] (NEW)
  → planning_service._display_telemetry(meta, token_count)
      → f"• Model: {model} | {meta.get('provider', 'unknown')}"  (NEW)
```

### Test Strategy
- **Driver**: Use `MockLlmClient` / real mock of `ILlmClient` to supply response objects with controlled `_hidden_params`.
- **Observer**: Capture `display_message` calls to verify Model line content.
- **Setup**: `TestEnvironment` with patched `ILlmClient` for unit/slice tests.
- **Safety**: All `getattr(response, "_hidden_params", {})` calls use fallback dict to prevent AttributeError.
