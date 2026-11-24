# Slice: Cache Telemetry
- **Status:** In Progress
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None (reads the same `meta.yaml` that slice 00-03 leaves untouched)
- **Specs:** None — the `meta.yaml` field set is an implementation contract documented in the session-manager component doc
- **Prototype:** None required
- **Component Docs:** [litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md), [prompt_manager.md](/docs/architecture/core/services/prompt_manager.md), [session_service.md](/docs/architecture/core/services/session_service.md), [planning_service.md](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `cache-telemetry`

## Goal
Turn the provider's cache accounting into persisted, inspectable session data and surface it as a cache ratio on the Session Cost line, so a payload layout change can be verified in production instead of inferred from probes.

## Context
- `LiteLLMAdapter._extract_detail_value(completion_response, "prompt_tokens_details", "cached_tokens")` already reads the provider's cached-token count, but only inside a cost-failure log path, so the value never leaves the adapter.
- `PlanningService._run_planning_phase` holds the completion `response` next to `token_count` and `turn_cost`, and calls `self._prompt_manager.log_telemetry(token_count, turn_cost)`.
- `PromptManager.update_turn_meta` writes `turn_cost` and `token_count` into `meta.yaml`. `token_count` is a `litellm.token_counter` estimate over the outgoing messages, not the provider's usage, and it feeds the context-budget display, so the two must not be conflated.
- `SessionService` accumulates `cumulative_cost` when it advances turn metadata, which is the pattern the new cumulative counters mirror.
- `PlanningService._display_telemetry` renders the cost line and already distinguishes "no pricing information" (`$???`) from a legitimately free model via the `cost_recorded` flag.
- Provider usage shape differs: caching providers report `usage.prompt_tokens` and `usage.prompt_tokens_details.cached_tokens`; non-caching providers omit the details object entirely.

## Scenarios
Primary user journeys and happy paths. These drive End-to-End Acceptance Tests in the Wiring deliverable.

> As a developer tuning payload layout, I want the session cost line to tell me how much of my input the provider served from cache.

```gherkin
Given a session on a provider that reports cache details
And the first turn reports no cached tokens
When the first turn's telemetry is displayed
Then the Session Cost line carries no cache suffix
And `meta.yaml` records `prompt_tokens` and `cached_tokens` as integers
```

```gherkin
Given the same session reaching a second turn whose prefix the provider serves from cache
When that turn's telemetry is displayed
Then the Session Cost line reads `(N% cached)` with N derived from the cumulative counters
```

```gherkin
Given a session on a provider that reports no cache details
When telemetry is displayed for any turn
Then the Session Cost line carries no cache suffix at all
```

## Edge Cases
Boundary conditions, errors, and validation edge cases. These drive granular Unit Tests in Core deliverables.

- **`cached_tokens` absent:** it persists as `0` and the suffix stays hidden until the cumulative cached count is positive, because a misleading `(0% cached)` trains the user to ignore the field.
- **No usage object at all:** both counters persist as `0` and the suffix stays hidden, because a provider without usage reporting is not a cache miss.
- **Ratio above 100%:** the percentage clamps at 100, because a provider that counts sub-blocks must not render an impossible ratio.
- **Free model with recorded zero cost:** the existing `cost_recorded` handling wins over the cache suffix, because `$0.0000` already states the truth and a suffix adds noise.
- **Unknown pricing:** `$???` renders with no cache suffix, because a missing price does not imply missing cache data.
- **Integer persistence:** every persisted counter is an `int`; a float or string from a provider payload is coerced or dropped, never stored.
- **Denominator zero:** a zero cumulative prompt count suppresses the suffix rather than dividing by zero.
- **Estimate untouched:** `token_count` keeps its meaning as a request estimate, so context-budget checks are unaffected by the new fields.

## Key Unknowns

- [x] [Technical] Whether the completion response can be inspected without leaking the provider object across the port. Design Sensitivity: resolved by an additive `ILlmClient` method taking the opaque response and returning a typed usage DTO; if the port cannot express it cleanly, the counters persist as unknown and the suffix stays hidden rather than guessing.
- [x] [Functional] Whether showing `(X% cached)` helps or clutters the cost line. Design Sensitivity: resolved as specified — suffix shown only when real cache data exists, suppressed otherwise; if the format reads badly in review, the presentation changes without touching the persisted fields.

## Impact
1. `[NEW]` `TokenUsage` — typed DTO carrying `prompt_tokens` and `cached_tokens`.
2. `[EXTEND]` `ILlmClient.get_token_usage` — additive port method over the opaque completion response the port already returns.
3. `[EXTEND]` `PromptManager.log_telemetry` / `update_turn_meta` and the `ISessionManager` turn-metadata contract — four new integer fields.
4. `[MIGRATE]` `PlanningService._display_telemetry` — appends the derived suffix under the omission rules.
5. `[MIGRATE]` existing telemetry and meta-key assertions that enumerate the persisted field set.

## Deliverables

- [x] **Interface** - Add the `TokenUsage` DTO, the additive `ILlmClient.get_token_usage` method, its `LiteLLMAdapter` implementation reusing the existing extraction, and the four new `meta.yaml` keys on the session-manager contract. One commit, because a port method without its only implementation leaves the suite red.
- [x] **Harness** - Add a fake `ILlmClient` usage stub that drives the cached-hit, zero-cache, and no-usage branches deterministically.
- [ ] **Wiring** - Thread the usage DTO from `PlanningService` into metadata persistence, writing zeros when the provider reports nothing and never emitting the suffix yet.
- [ ] **Core** - Accumulate the cumulative prompt and cached counters in `SessionService`, derive the integer percentage, and append `(X% cached)` in `_display_telemetry` under the documented omission rules.
- [ ] **Migration** - Update existing telemetry-output and meta-field assertions, and document the new keys in the session-manager component doc.

## Implementation Notes
The adapter owns provider-shape parsing; the core sees only integers. Cumulative counters live beside `cumulative_cost` so the whole display renders from one meta object.

### Interface delivered
- `TokenUsage` is a frozen dataclass in `core/domain/models/token_usage.py`, re-exported from the models package. An absent provider field reads as `0`, never as a guess.
- `ILlmClient.get_token_usage` is a concrete, defaulted method returning a zeroed `TokenUsage`, mirroring the `get_text_token_count` precedent. An abstract method would have broken the three contract-test stubs outside this deliverable's scope, and the zeroed default encodes the rule that an unobservable count is never rendered as a cache estimate.
- `LiteLLMAdapter.get_token_usage` reuses the existing `_extract_usage_value` and `_extract_detail_value` readers. Both accept only real `int` values, so a string or float from a provider payload is dropped rather than stored.
- `_log_cost_failure` is deliberately unchanged: its diagnostic payload distinguishes `None` from `0`, so it must not be rerouted through the zero-filling accessor.
- The four meta keys are declared once as `TURN_USAGE_META_KEYS` in the session-manager port module and pinned by a contract test; the persistence and display work lands in Wiring and Core.
- The DTO intentionally does not assert `cached_tokens <= prompt_tokens`: a provider may count sub-blocks, and clamping belongs to the display layer.
- Environment repair: `.venv/bin/pytest` carried a shebang pointing at the former `TeDDy3` checkout; `uv sync --reinstall` regenerated the console scripts without moving `uv.lock`.

### Harness delivered
- `FakeLlmClient` (`tests/harness/setup/fake_llm_client.py`) is a hand-written in-memory `ILlmClient`, mirroring the `fake_pdf_extractor` precedent rather than a spec-bound mock. `get_token_usage` pops a scripted `TokenUsage` queue and drains to a zeroed `TokenUsage`, so the cached-hit, zero-cache, and no-usage branches are all driven deterministically; `enqueue_usage` appends to the queue and `usage_calls` records every response inspected.
- `get_completion` returns a minimal well-formed response (`choices[0].message.content` and a fixed `.model`) so `PlanningService` can extract plan content and read the serving model without a live provider. The remaining port operations return neutral defaults.
- The fixture is registered in `mocks.py`, re-exported through `composition.py`, and threaded into `tests/conftest.py`, so pytest discovers it globally. `mock_llm_client` stays a spec-bound mock; `FakeLlmClient` is the real in-memory double a Wiring test injects when it needs the actual usage branch.
- Harness tests live at `tests/suites/unit/test_fake_llm_client_harness.py`, matching the `test_*_harness.py` convention: parameterized branch coverage, queue-drain behavior, completion usability, port conformance, and fixture registration.

## Verification
1. **Persisted counters:**
   Run a two-turn session with `teddy start -m "smoke check"`, then run `cat .teddy/sessions/<session>/02/meta.yaml`.
   Verify `prompt_tokens`, `cached_tokens`, `cumulative_prompt_tokens` and `cumulative_cached_tokens` are present as integers.
2. **Console suffix:**
   Watch the telemetry line printed before the second plan.
   Confirm it reads `• Session Cost: $...  (N% cached)` with a plausible N.
3. **Non-caching provider:**
   Point `llm.model` at a provider that reports no cache details and run one turn.
   Confirm the cost line carries no cache suffix.
