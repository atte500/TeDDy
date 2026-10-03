# Slice: Cost Calculation Accuracy

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc, Milestone 0 prefix)
- **Specs:** [Task Brief 00-22](/docs/project/tasks/00-22-cost-calculation-accuracy.md)
- **Prototype:** N/A (empirical probe matrix S1–S6b recorded in the Task Brief Context section)
- **Component Docs:** [litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md), [planning_service.md](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `cost-calculation-accuracy`

## Business Goal

Ensure session cost accounting reflects true provider spend — including cached-token discounts and cache-write premiums — so the YOLO `max_session_cost` guardrail and user-facing cost telemetry are trustworthy.

Three defects are fixed:
1. **Hydrator cache-pricing gap** — `OpenRouterMetadataHydrator._find_model` broadcasts only `input_cost_per_token`/`output_cost_per_token`, so hydrated OpenRouter models lack `cache_read_input_token_cost`/`cache_creation_input_token_cost` in `litellm.model_cost`. Result: cached tokens billed at **$0** (silent underestimate), and Anthropic-shaped usage (prompt, creation, read) can produce a **negative** prompt cost.
2. **Silent cost-failure swallowing** — `LiteLLMAdapter.get_completion_cost` swallows every exception into a bare `return 0.0` with no logging (a Failure Transparency violation); under-counted spend never trips the guardrail.
3. **Retry-cost loss** — the planning retry loop overwrites `turn_cost` per attempt, so billed empty-response attempts that trigger a retry vanish from the session total.

## Scenarios

> As a TeDDy user, I want session cost telemetry to reflect cached-token discounts so that my spend display and the max-cost guardrail are trustworthy.

```gherkin
Given a configured OpenRouter model whose live catalog entry carries cache-read and cache-write rates
When a turn completes with cached prompt tokens
Then the computed turn cost applies the cache-read discount (cached tokens are never billed at $0)
And no negative prompt cost is produced for Anthropic-shaped usage
```

> As a TeDDy user running a session that retries, I want every billed LLM attempt counted so that my session total and the max-cost guardrail are accurate.

```gherkin
Given the first planning attempt returns an empty response that is still billed
  And the second attempt succeeds with a valid plan
When the planning turn finalizes
Then the turn cost equals the sum of both attempts' costs
  And the session's cumulative cost includes the failed attempt's cost
```

> As a TeDDy maintainer, I want cost-computation failures to be visible so that silently under-counted spend can be diagnosed without breaking successful completions.

```gherkin
Given a completion for a model that HAS pricing metadata in the registry
When litellm's cost computation raises
Then a WARNING is logged carrying the model identity and usage details
  And the adapter returns 0.0 so the successful completion is not penalised
```

## Edge Cases

- **Unpriceable model**: If a model has NO pricing metadata in `litellm.model_cost`, then a cost-computation failure is logged at DEBUG (not WARNING), because it is an expected miss (mirrors the TUI `$???` placeholder).
- **Non-numeric cache rate**: If a catalog entry's cache rate is non-numeric (e.g. `"$0.000001"`), then the hydrator returns `None` for that model, because the existing `ValueError`/`TypeError` guard semantics are preserved.
- **Absent cache keys**: If a catalog entry omits cache rates, then the pricing dict omits `cache_read_input_token_cost`/`cache_creation_input_token_cost`, because injecting a 0.0 rate would reproduce the $0-billing defect.
- **Zero cache rate**: If a catalog entry carries a cache rate that parses to 0.0, then the key is omitted (present-and-`> 0` gating), because a 0.0 rate is equivalent to the defect.
- **Single-attempt success**: If the first attempt succeeds, then its cost is counted exactly once, because accumulation must not double-count the successful attempt.
- **Hydration-failure fallback**: If hydration fails to supply metadata after a cost-computation exception, then the adapter still returns 0.0 and logs the failure, because the `0.0` return contract is preserved in all paths.
- **Registry-model regression**: If a model is already registered in litellm with cache rates (e.g. `gpt-4o`), then its exact discounted math is unchanged, because the fix touches only hydrated-model metadata.

## Key Unknowns

- [x] [Technical] OpenRouter catalog cache-pricing key names — resolved in the Task Brief: `input_cache_read` and `input_cache_write` are the documented per-token cache keys; the hydrator maps them to litellm's `cache_read_input_token_cost` / `cache_creation_input_token_cost`. (Verify against the live catalog at implementation time per Step 1.)
- [x] [Technical] Does `_find_model` need float conversion for the new keys, or does `_hydrate_all_candidates.safe_pricing` handle it downstream? — resolved during reconnaissance: `_find_model` reads the pricing dict directly and float-converts, returning a formatted pricing dict; `_hydrate_all_candidates.safe_pricing` re-floats every key defensively, so new keys flow through automatically. The float conversion belongs in `_find_model` alongside the existing prompt/completion conversion.

## Implementation Plan

Root-cause evidence and the empirical probe matrix (S1–S6b) live in the Task Brief. Three production files and three test files are touched; no new ports, no signature changes to shared seams, and no composition-root changes.

1. **Hydrator cache rates** — `OpenRouterMetadataHydrator._find_model` (openrouter_hydrator.py:147-155) currently broadcasts only `input_cost_per_token`/`output_cost_per_token`. Extend it to read `input_cache_read`/`input_cache_write` with defensive `.get()`, float-convert under the existing guard, and include `cache_read_input_token_cost`/`cache_creation_input_token_cost` ONLY when present AND parsed `> 0`. Verify the catalog key names against `https://openrouter.ai/api/v1/models` first.
2. **Mock catalog** — extend `OPENROUTER_MODELS_RESPONSE` (tests/harness/setup/openrouter_mock_data.py) with string-valued cache keys on one model and keep a second model WITHOUT cache keys.
3. **Tiered cost-failure logging** — add a module logger to `LiteLLMAdapter` and a `_log_cost_failure` helper; call it before each `return 0.0` in `get_completion_cost` (litellm_adapter.py:237-263). Keep the `0.0` return contract.
4. **Retry-cost accumulation** — `PlanningService._perform_generation_with_retry` (planning_service.py) accumulates `turn_cost += attempt_cost` instead of overwriting per attempt.

The `Wiring` deliverable has no new cross-boundary wiring to establish (the cost pipeline already exists end-to-end); consistent with 00-21's final Wiring acceptance deliverable, it is a final behavioral gate rather than a hardcoded-data tracer bullet.

Test Harness strategy:
- Hydrator tests re-use the established `openrouter_mock` / `pytest_httpserver` redirection and the `FakeRegistryCache` fixture (Slice 00-20 made the hydrator construction cache-injectable; pass `cache_path=None` to keep the network path).
- Logging tests use `caplog` (the project's sole logging-assertion convention) over a spec-bound config double; no bare mocks, no module patching.
- Retry-accumulation tests use the existing `POSIXPathMock` / `register_mock` conventions over `PlanningPorts`.
- The Wiring acceptance gate drives the CLI test driver with the mocked LLM client's `get_completion`/`get_completion_cost` side effects.

Semantic deduplication (census, turns 5-6): no existing test asserts cache-pricing keys, tiered cost-failure logging, or retry-cost accumulation; the existing `test_get_completion_cost_*` tests pin only the hydration-retry and graceful-fallback behaviors (preserved unchanged).

## Deliverables

- [ ] **Harness** - Extend the OpenRouter mock catalog (`tests/harness/setup/openrouter_mock_data.py`): add string-valued cache-pricing keys (`input_cache_read`, `input_cache_write`) to one model (`deepseek/deepseek-v4-flash`) and keep a second model (`google/gemini-2.0-flash-001`) WITHOUT cache keys, so the hydrator Logic tests can assert both cache-key flow and defensive omission.
- [ ] **Logic** - Broadcast cache-pricing rates from `OpenRouterMetadataHydrator._find_model` (`cache_read_input_token_cost`/`cache_creation_input_token_cost`, present-and-`> 0` gating, defensive `.get()`, preserved `ValueError`/`TypeError` guard) — bundle the unit tests (cache keys flow with correct floats; entry without cache keys omits them; non-numeric cache values degrade safely).
- [ ] **Logic** - Tiered cost-failure logging in `LiteLLMAdapter.get_completion_cost` (module logger + `_log_cost_failure` helper extracting model identity and a defensive usage summary; DEBUG for unpriced models, WARNING for priced models; `exc_info=True`; `0.0` return contract unchanged) — bundle the unit tests.
- [ ] **Logic** - Accumulate retry costs in `PlanningService._perform_generation_with_retry` (`turn_cost += attempt_cost`, computed into a local first) — bundle the unit tests (multi-attempt sum; single-attempt billed once).
- [ ] **Wiring** - Final behavioral gate: end-to-end session cost accrual through the CLI boundary (a retried turn's `turn_cost`/`cumulative_cost` reflects the SUM of all billed attempts) — acceptance test via the CLI test driver.

## Verification

- [ ] `uv run pytest tests/suites/unit/adapters/outbound/test_openrouter_hydrator.py tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py tests/suites/unit/core/services/test_planning_service_retries.py tests/suites/unit/core/services/test_planning_service.py -q` — all green.
- [ ] Full test suite via the post-commit hook (never bypassed).
- [ ] Regression check: models WITHOUT cache pricing bill exactly as before; registry models with cache rates (e.g. gpt-4o) still produce exact discounted math.
- [ ] Optional manual probe: run a session turn against a cache-priced OpenRouter model with prompt caching active; confirm `turn_cost` reflects the cache-read discount (no $0-billed cached tokens; no negative prompt cost on Anthropic-shape usage).
