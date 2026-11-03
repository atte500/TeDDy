# Slice: Cost Estimation Precision by Resolved Vendor
- **Status:** In Progress
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [ILlmClient](/docs/architecture/core/ports/outbound/llm_client.md), [PlanningService](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `cost-precision`

## Goal
Compute precise USD cost tied to the vendor/hoster that actually served the request, so both the TUI session cost display and `max_session_cost` guardrail enforcement reflect actual billed spend rather than the configured model's single catalog price.

## Context
- `OpenrouterConfig.transform_request` injects `usage.include=true` unconditionally, so OpenRouter always returns `usage.cost` and no caller-side flag is required.
- `OpenrouterConfig.transform_response` copies `usage.cost` into `_hidden_params["additional_headers"]["llm_provider-x-litellm-response-cost"]` as a `float`.
- On a successful non-streaming completion, litellm's `set_hidden_params` populates `response._hidden_params["response_cost"]` by calling `logging_obj._response_cost_calculator(...)`. That calculator prefers `get_response_cost_from_hidden_params` — which reads the OpenRouter header — before any registry recompute, so the returned response already carries the vendor-reported cost.
- `litellm.completion_cost(completion_response=...)` — the function the adapter calls directly — does NOT read `_hidden_params["response_cost"]` or the OpenRouter header. It recomputes from `completion_response.model` against the registry, and `litellm.model_cost` holds no `openrouter/*` keys, so an OpenRouter model prices at the hydrator's single catalog row or `0.0`.
- `get_response_cost_from_hidden_params(hidden_params)` returns the reported cost (`float`) from `additional_headers["llm_provider-x-litellm-response-cost"]`, or `None` when the header is absent.
- `LiteLLMAdapter.get_completion_cost`: calls `litellm.completion_cost(completion_response=...)` and thereby discards the already-reported cost; it never forwards `model_override` to the pricing call.
- `OpenRouterMetadataHydrator._find_model`: reads only the catalog `pricing.prompt`, `pricing.completion`, and cache rates; it has no per-upstream-provider price because the reported cost is the source of truth.
- `PlanningService._perform_generation_with_retry`: accumulates `turn_cost` across retries; that value feeds both `cumulative_cost` telemetry and the loop guard's `max_session_cost` checks.
- `PlanningService._display_telemetry`: shows `$???` when `context_window <= 0` or `supports_pricing(model)` is false; it does not consider the recorded reported cost.
- `PromptManager.update_meta`: stores `actual_model` from `response.model`; `_resolve_cost_model` prefers `model_override` over the response identity for diagnostics only.
- Milestone 6 "Provider resolution behind ILlmClient" will consolidate provider resolution; this slice MUST NOT introduce a second divergent resolution path, and any new resolution seam must be shaped so M6 can subsume it.

## Scenarios

> As a user whose OpenRouter request routes to an upstream provider with a distinct per-token price, I want the reported session cost to reflect the actual billed cost, so my figure matches my spend.

> As a user relying on the `--max-cost` guardrail, I want the accumulated cost to reflect actual billed prices, so the guardrail triggers accurately.

```gherkin
Given a completion whose `_hidden_params["response_cost"]` carries a reported cost
When I run a turn with a configured model that differs from the response identity
Then the turn cost equals the reported cost, not the catalog recompute
```

```gherkin
Given an unpriced model with no reported cost
When I run a turn
Then the display shows $??? and no exception is raised
```

## Edge Cases
- **No reported cost**: If `_hidden_params` is absent or not a dict, then `litellm.completion_cost` is called, because the response carries no reported value.
- **`response_cost` absent or `None`**: If the key is absent or `None`, then `litellm.completion_cost` is called, because only a concrete number is authoritative.
- **Non-finite reported cost**: If the reported value is `NaN` or infinite, then it is treated as absent and the recompute runs, because a non-finite number cannot be a spend.
- **Free model**: If the reported cost is `0.0`, then `0.0` is returned without a recompute, because a free model is a valid price, not an error.
- **Header-only fallback**: If `response_cost` is absent but the OpenRouter header is present, then the header value is returned, because it is the same reported spend.
- **Local endpoint**: If `llm.api_base` points at a local host, then no OpenRouter header is present and the recompute runs, because the endpoint is the source of truth.
- **Unmapped model**: If no reported cost exists and the model is not in `litellm.model_cost`, then hydration runs once and falls back to `0.0`, because the cost contract must never raise.
- **Retry accumulation**: If an attempt retries, then each attempt's reported cost is added to `turn_cost`, because a dropped cost silently under-reports the session total.
- **Display gate**: If the model has no catalog pricing but a reported cost was recorded, then the display shows the recorded cost rather than `$???`, because the reported cost is known.
- **Diagnostics identity**: If a reported cost is used, then the diagnostic summary names the reported-cost source so an anomaly is diagnosable.

## Key Unknowns

None — all unknowns resolved during Discovery and the alignment approval gate. Display-gate decision (Option B, approved 2026-11-03): relax the `$???` gate to show a recorded cost whenever one was recorded, using an explicit recorded-cost signal rather than `cost > 0`, because a free model legitimately records `0.0`.

## Impact
Map affected components using non-breaking steps (expand -> migrate -> contract) to protect existing consumers.

1. `[EXPAND]` `LiteLLMAdapter.get_completion_cost` — Read the reported cost from `_hidden_params` (preferring `response_cost`, then the OpenRouter header) before `litellm.completion_cost`; preserve the `0.0` fallback, the hydration retry, and tiered logging.
2. `[MIGRATE]` `PlanningService._perform_generation_with_retry` — No signature change; verified cost accuracy across retries.
3. `[MIGRATE]` `PlanningService._display_telemetry` — Relax the `$???` gate to show a recorded reported cost.
4. `[CLEANUP]` `_resolve_cost_model` — Name the reported-cost source in the diagnostic summary so anomaly logs reflect the priced identity.

## Deliverables

- [x] **Wiring** - Acceptance test: a completion whose `_hidden_params["response_cost"]` is a concrete float returns that value without calling `litellm.completion_cost`; a completion without it falls back to `litellm.completion_cost`. Implement the reported-cost read, preferring `_hidden_params["response_cost"]`, then `get_response_cost_from_hidden_params`, then the existing recompute.
- [ ] **Core** - Cover the read edge cases with unit tests: non-dict hidden params, absent/`None` value, non-finite value, free-model `0.0`, and header-only fallback.
- [ ] **Migration** - Relax the `_display_telemetry` `$???` gate so a recorded reported cost shows even when `supports_pricing` is false, without masking a genuinely unpriced model (a free model still reads `$0.0000`). Introduce an explicit "cost was recorded" signal (Option B) so the gate keys off recorded-ness rather than `supports_pricing`, because a free model legitimately records `0.0` and cannot be distinguished from "no cost" by `cost > 0`.
- [ ] **Cleanup** - Align `_resolve_cost_model` (diagnostic summary) with the reported-cost source so anomaly logs report the identity actually priced.

## Implementation Notes
Discovery resolved the technical unknowns against the installed litellm sources. The reported cost is already computed by litellm and stored on the response; the adapter simply discards it by calling `completion_cost` directly. No provider-keyed price table or `custom_llm_provider` forwarding is needed. Existing telemetry tests keep passing because a bare `Mock()` response yields a non-dict `_hidden_params` and falls through to the recompute. All unknowns are resolved; the display-gate decision is Option B, approved at the alignment gate on 2026-11-03. Route to the Developer.

- **Wiring (2026-11-03):** Added `LiteLLMAdapter._reported_cost`, which reads `_hidden_params["response_cost"]` and returns it before the recompute; `get_completion_cost` now prefers it, then falls through to `litellm.completion_cost`. The helper returns `None` for a non-dict holder, an absent key, a `None` value, or an unconvertible value, preserving the `cost_never_raises` invariant. Deviation: the slice labels Wiring an *acceptance* test, but the behavior is only reachable at the adapter boundary (the acceptance harness mocks `ILlmClient` wholesale), so the tracer-bullet tests live in `tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py` using `SimpleNamespace` + a minimal `_FakeCostLitellm` double (no bare `Mock`). The OpenRouter-header fallback (`get_response_cost_from_hidden_params`) and the non-finite guard are deliberately deferred to Core so Core gets a genuine Red.

## Verification
1. **Reported cost precedence:**
   Run a small OpenRouter session turn.
   Verify `• Session Cost:` matches OpenRouter's reported `usage.cost` for the response rather than the catalog price.
2. **Unpriced fallback:**
   Configure `llm.model` to an unmapped model and run a turn.
   Verify the display still shows `$???` (no cost recorded) and no exception is raised.
3. **Guardrail enforcement:**
   Set `--max-cost` to a low value and trigger multiple turns.
   Verify the guardrail triggers based on the accurately accumulated reported cost.
