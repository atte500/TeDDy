# Task: Cost Calculation Accuracy — Hydrator Cache Rates, Tiered Cost-Failure Logging, Retry-Cost Accumulation

## Business Goal
Ensure session cost accounting reflects true provider spend — including cached-token discounts and cache-write premiums — so the YOLO `max_session_cost` guardrail and user-facing cost telemetry are trustworthy.

## Context
Empirical verification of the cost pipeline was completed 2026-10-02 against litellm 1.83.7 (diagnostic spike `spikes/debug/cost-calculation-accuracy.py`, since deleted; results recorded here).

**Pipeline:** `PlanningService._perform_generation_with_retry` → `LiteLLMAdapter.get_completion_cost` (full delegation to `litellm.completion_cost`; no manual formula) → `PromptManager.update_meta` (`turn_cost`) → `SessionService` (`cumulative_cost`) → TUI display and YOLO guardrail.

**Empirical probe matrix (S1–S6b):**

| Scenario | Result |
|---|---|
| S1 — baseline naive formula, registry model (gpt-4o) | Exact match to `tokens x price` |
| S2 — `reasoning_tokens=20` within `completion_tokens=50` | Identical to baseline: reasoning tokens billed **once**, as output. No double-billing. |
| S3 — `cached_tokens=40` on gpt-4o (registry model with cache rates) | Exact discounted math: `(100−40)×input + 40×cache_read + 50×output`. litellm applies cache discounts when `model_cost` carries cache rates. |
| S4 — `cached_tokens=40` on hydrator-metadata model (no cache keys) | Cached tokens billed at **$0/token** — silent UNDERestimate ($0.00016 vs ~$0.00019 true). |
| S6a — Anthropic-exclusive shape (prompt=20, creation=30, read=20) on hydrator model | **NEGATIVE unclamped prompt cost** ($0.00007 < completion-only $0.0001): litellm computes `(prompt − creation − read)`. |
| S6b — inclusive stress (prompt=100, creation=30, read=20) on hydrator model | Subtractive mechanism confirmed ($0.00015 = 50 non-cached × input + completion). |

**Root causes (in priority order):**
1. `OpenRouterMetadataHydrator._find_model` (lines 147–155) broadcasts only `input_cost_per_token` / `output_cost_per_token`. OpenRouter's catalog pricing payload carries cache rates (documented per-token keys: `input_cache_read`, `input_cache_write`) that are never read → hydrated models lack `cache_read_input_token_cost` / `cache_creation_input_token_cost` in `litellm.model_cost` → S4 ($0-billing) and S6a (negative billing).
2. `get_completion_cost` (litellm_adapter.py:237–263) swallows **all** exceptions into a silent `return 0.0` with no logging — a Failure Transparency violation. Under-counted spend never trips the YOLO `max_session_cost` guardrail.
3. The planning retry loop overwrites `turn_cost` per attempt (`turn_cost = self._llm_client.get_completion_cost(...)` inside the loop) — billed empty-response attempts vanish from the session total.

**Constraints and decisions (user-approved 2026-10-02):**
- The adapter MUST keep the `0.0` return contract: cost is non-critical-path telemetry on an already-successful completion. The fix adds visibility, not raises.
- Tiered logging (non-intrusive per user constraint): `DEBUG` (or silence) for expected unpriced-model misses (mirrors the TUI `$???` placeholder); `WARNING` only when a **priced** model's cost computation raises (anomaly — data silently lost). The empirically proven bugs (S4/S6a) never raise — litellm returns wrong values silently — so Fix 1 is the actual accuracy fix; the logging is the residual safety net.
- The hydrator fix MUST use defensive `.get()` so absent cache keys in the catalog degrade to current behavior.
- No adapter registry-injection changes needed: `_hydrate_all_candidates` already float-converts every pricing key via its `safe_pricing` loop, so new keys flow through automatically.
- Residual accepted limitation: raw Anthropic-API usage shapes may still mis-bill (litellm assumes inclusive subtraction of cache tokens from `prompt_tokens`); OpenRouter — TeDDy's documented default provider — normalizes usage, and litellm-registered models are already correct.

## Implementation Steps

### Step 1: Broadcast cache-pricing rates from the hydrator
- **File:** [src/teddy_executor/adapters/outbound/openrouter_hydrator.py](/src/teddy_executor/adapters/outbound/openrouter_hydrator.py)
- **Change:** First, verify the exact cache-pricing key names against the live catalog (`https://openrouter.ai/api/v1/models`); OpenRouter documents `input_cache_read` and `input_cache_write` as per-token cache prices — adjust if the payload differs. Then, in `_find_model`, read the cache rates with `pricing.get(...)`, parse them with `float()` alongside the existing prompt/completion conversion (keeping the existing `ValueError`/`TypeError` guard semantics), and add `cache_read_input_token_cost` / `cache_creation_input_token_cost` to the returned pricing dict **only when present and > 0** (a parsed 0.0 rate must be omitted — injecting a 0.0 `cache_read_input_token_cost` would reproduce the S4 $0-billing bug). Absent keys → keys omitted → behavior identical to today.

### Step 2: Extend the harness mock catalog with cache pricing
- **File:** [tests/harness/setup/openrouter_mock_data.py](/tests/harness/setup/openrouter_mock_data.py)
- **Change:** Add cache keys to at least one model's pricing payload (e.g., `deepseek/deepseek-v4-flash`: `"input_cache_read": "0.0000001"`, `"input_cache_write": "0.00000125"` — string-valued, matching the catalog's string-number shape) so hydrator tests can assert the new keys flow through. Keep (or add) a second model WITHOUT cache keys to pin the defensive-omission behavior.

### Step 3: Tiered cost-failure logging in the adapter
- **File:** [src/teddy_executor/adapters/outbound/litellm_adapter.py](/src/teddy_executor/adapters/outbound/litellm_adapter.py)
- **Change:** Add a module logger (`logging.getLogger(__name__)`) and a private helper (e.g., `_log_cost_failure(exc, completion_response, model_override)`) that extracts: (a) model identity — `model_override` → `completion_response.model` → config `llm.model`; (b) a defensive usage summary — `prompt_tokens`, `completion_tokens`, plus `cached_tokens` and `reasoning_tokens` from the prompt/completion details objects when present (shapes vary per provider; extract defensively); and logs with `exc_info=True`. Call the helper immediately before each `return 0.0` in `get_completion_cost`, with tiered levels: `logger.debug` when the resolved model has NO pricing metadata in `litellm.model_cost` (expected miss — same reason the TUI shows `$???`); `logger.warning` when the model IS priced (`input_cost_per_token` present in its registry entry) yet `completion_cost` raised (anomaly). Keep the `0.0` return contract unchanged in all paths.

### Step 4: Accumulate retry costs in the planning loop
- **File:** [src/teddy_executor/core/services/planning_service.py](/src/teddy_executor/core/services/planning_service.py)
- **Change:** In `_perform_generation_with_retry`, replace the per-attempt overwrite (`turn_cost = self._llm_client.get_completion_cost(...)`) with accumulation: compute the attempt's cost into a local, then `turn_cost += attempt_cost`, so billed empty-response attempts that trigger a retry remain in the session total and the final successful attempt's cost is included exactly once.

### Step 5: Hydrator unit tests
- **File:** [tests/suites/unit/adapters/outbound/test_openrouter_hydrator.py](/tests/suites/unit/adapters/outbound/test_openrouter_hydrator.py)
- **Change:** Add tests: (a) a catalog entry with cache keys yields `cache_read_input_token_cost` / `cache_creation_input_token_cost` in `get_metadata`'s pricing dict with correct float values; (b) an entry without cache keys yields no such keys (defensive omission); (c) non-numeric cache values degrade safely (no crash, keys omitted).

### Step 6: Adapter logging unit tests
- **File:** [tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py](/tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py)
- **Change:** Add tests for the tiered logging: (a) a priced model whose `completion_cost` raises → a WARNING is emitted carrying model identity and usage fields; (b) an unmapped/unpriced model → DEBUG level (no WARNING); (c) the `0.0` return contract is preserved in both paths. Use the project's mock-registration conventions; no bare mocks, no module patching.

### Step 7: Retry-cost accumulation unit tests
- **File:** [tests/suites/unit/core/services/test_planning_service_retries.py](/tests/suites/unit/core/services/test_planning_service_retries.py)
- **Change:** Add a test where the first attempt returns empty content (and is billed) and the second attempt succeeds: assert the returned `turn_cost` equals the SUM of both attempts' costs (previously only the last attempt's cost survived). Add a companion test asserting a single-attempt success is billed exactly once.

## Verification
1. `uv run pytest tests/suites/unit/adapters/outbound/test_openrouter_hydrator.py tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py tests/suites/unit/core/services/test_planning_service_retries.py tests/suites/unit/core/services/test_planning_service.py -q` — all green.
2. Full test suite via the post-commit hook (never bypassed).
3. Regression check: models WITHOUT cache pricing bill exactly as before (S1/S2 math unchanged); registry models with cache rates (e.g., gpt-4o) still produce exact discounted math (S3).
4. Optional manual probe: run a session turn against a cache-priced OpenRouter model with prompt caching active and confirm `turn_cost` reflects the cache-read discount — no $0-billed cached tokens (S4) and no negative prompt cost on Anthropic-shape usage (S6a).
