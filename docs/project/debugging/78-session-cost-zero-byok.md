# Bug: Session Cost Shows $0.0000 Under OpenRouter BYOK
- **Status:** Resolved
- **Milestone:** [Milestone 4: Terminal User Interface](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Vertical Slice:** [00-11-cost-precision.md](/docs/project/slices/00-11-cost-precision.md)
- **Specs:** [interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Symptoms
Expected: with a paid model configured against OpenRouter and a billable response, the right-panel metadata shows a session cost that reflects spend (or the `$???` placeholder when the model is genuinely unpriced).

Actual: the panel shows `• Session Cost: $0.0000` while running a session with BYOK credentials on OpenRouter. The user cannot tell whether a zero is the correct BYOK figure or a defect in cost extraction, accumulation, or rendering.

Minimal reproduction steps (reported; the hermetic MRE below stands in for the live run):
1. Configure a session against OpenRouter with BYOK provider keys supplied to OpenRouter.
2. Run an interactive session and complete at least two turns.
3. Observe the `• Session Cost:` line in the right panel / console telemetry.
4. Local hermetic MRE `spikes/debug/session-cost-zero-byok/01-openrouter-byok-cost-display-mre.py` drives the real `LiteLLMAdapter` and the real `_display_telemetry` across eight response shapes; the verdict table is in the Causal Model.

## Context & Scope
### Regressing Delta
`34654549 feat(cost-precision): prefer reported completion cost over registry recompute` and `9d7a4269 feat(cost-precision): guard reported cost read and add header fallback` in [`litellm_adapter.py`](/src/teddy_executor/adapters/outbound/litellm_adapter.py) (recently touched again by `16e68d1b fix(cost-precision): align cost-failure diagnostics with the priced identity`).

Those commits made any response-reported figure authoritative before the registry recompute. That is correct for a non-BYOK request, where the reported figure is OpenRouter's actual charge. It is wrong under BYOK, where the reported figure is OpenRouter's own waived fee. The gap those commits exposed is an omission rather than a defect they introduced: the adapter never read `usage.cost_details.upstream_inference_cost`, and slice 00-11's Context section documents the assumption that made that acceptable ("no per-upstream-provider price because the reported cost is the source of truth"). Before the reported-cost read, a BYOK turn fell through to a catalog recompute and showed a wrong nonzero figure; after it, the same turn shows a trusted `$0.0000`.

### Environmental Triggers
- Provider: OpenRouter, with BYOK provider keys (the user's own upstream keys) rather than OpenRouter-hosted routing.
- Configuration: `llm.model` set to an OpenRouter-routed model; `llm.api_key` is an OpenRouter key.
- Local endpoints are out of scope: no OpenRouter cost header exists there.

### Ruled Out
- **Extraction/summation/rendering defects for a real reported price**: MRE cases 1 and 3 return the reported figure, and case 6 recomputes correctly after hydration. The display path is not the defect.
- **`$???` for genuinely unpriced models**: MRE case 7 still shows the placeholder, so the recorded-cost gate does not mask a truly unpriced model.
- **Provider-side capture**: installed litellm injects `usage.include=true` (`openrouter/chat/transformation.py:173`) and copies `usage.cost` into `llm_provider-x-litellm-response-cost` (`:216-228`); `get_response_cost_from_hidden_params` reads exactly that header.

## Diagnostic Analysis
### Causal Model
Verified from source, not assumed:

- `LiteLLMAdapter.get_completion_cost` reads three sources in order: a positive `usage.cost_details.upstream_inference_cost` (OpenRouter BYOK spend) plus any reported fee; then `_hidden_params["response_cost"]`; then `_hidden_params["additional_headers"]["llm_provider-x-litellm-response-cost"]`. A non-dict holder, absent key, `None`, or non-finite value falls through to the next source and ultimately to `litellm.completion_cost(completion_response=...)`. The upstream read is guarded by `isinstance(cost_details, dict)` because litellm preserves the field as a plain dict.
- Any real price (reported, or a successful recompute including a free-model `0.0`) sets `_teddy_cost_recorded = True` on the response. The recompute-failure fallback `0.0` is deliberately left unmarked.
- `PlanningService._perform_generation_with_retry` accumulates `turn_cost` across retries and returns it. `generate_plan` OR-sets `meta["cost_recorded"]` only when the response flag `is True`.
- `SessionService._persist_next_meta` computes `cumulative_cost = previous + turn_cost` and carries a `True` recorded flag forward.
- `PlanningService._display_telemetry` runs inside `_run_planning_phase` BEFORE the completion call for that turn. It formats `meta["cumulative_cost"]` as `$%.4f` and emits `$???` only when `context_window <= 0` or neither `supports_pricing(model)` nor `cost_recorded` holds.

Two consequences follow directly from that model. First, the panel always shows the inherited cumulative cost, so the first turn of any session legitimately renders `$0.0000` once the gate passes. Second, a provider-reported `0.0` is treated as a valid recorded price, so under a provider that reports zero spend the accumulated figure never rises.

The hermetic MRE (`spikes/debug/session-cost-zero-byok/01-openrouter-byok-cost-display-mre.py`) drove the real adapter and telemetry across eight shapes and produced this verdict table:

| Shape | `cost` | `recorded` | Panel |
| --- | --- | --- | --- |
| 1 reported `response_cost` | 0.0012345 | True | `$0.0012` |
| 2 first-turn telemetry (pre-response cumulative) | 0.004 (turn only) | True | `$0.0000` |
| 3 header-only reported cost | 0.0021 | True | `$0.0021` |
| 4 reported `0.0` (free model) | 0.0 | True | `$0.0000` |
| 5 unmapped + hydration miss, served identity displayed | 0.0 | False | `$???` |
| 5b unmapped + hydration miss, configured identity displayed | 0.0 | False | `$0.0000` |
| 6 unmapped + hydration success | 0.0105 | True | `$0.0030` (inherited) |
| 7 unpriced model, nothing recorded | 0.0 | False | `$???` |

Three conclusions follow. First, extraction, summation, and rendering are correct for every shape with a real reported price (1, 3) and for a genuinely unpriced model (7). Second, the displayed identity decides the gate: case 5b prints a confident `$0.0000` for a failed recompute whenever the displayed identity has catalog pricing while the recompute prices a different, unmapped identity that hydration cannot resolve — a real silent under-report, but reachable only when no reported cost exists. Third, under OpenRouter BYOK, where a reported cost always exists, a `$0.0000` can only be the provider's own `usage.cost`; OpenRouter's docs say that value is its BYOK fee (5% of list, waived by a monthly free allowance) and that the actual provider spend is `usage.cost_details.upstream_inference_cost`.

The fix closes that third conclusion. `_reported_cost` now prefers a positive upstream spend, so a BYOK turn records the user's real provider cost and `cumulative_cost` rises across turns. The pre-response ordering is unchanged by design, so the first turn of any session still prints the inherited `$0.0000` before its completion runs; from turn 2 onward the panel shows accumulated real spend instead of a flat zero.

### Discrepancies
- [x] Reported `$0.0000` under BYOK versus an expectation of nonzero spend (Resolved: the display path is correct; OpenRouter's BYOK fee on `usage.cost` is `0` under the monthly free allowance, and the user's real spend is `usage.cost_details.upstream_inference_cost`, which the adapter discarded).
- [x] Unknown whether OpenRouter sets `usage.cost` to `0` under BYOK and whether `usage.cost_details.upstream_inference_cost` survives onto the litellm response `usage` (Resolved: OpenRouter documents the fee of 5% waived by a $25k/month allowance; litellm's `Usage` model preserves `cost_details` via `extra: allow`, confirmed by direct construction; a sandbox replica now reads it).
- [x] Unknown whether the observed zero is simply the pre-response telemetry of a fresh session (Resolved: acceptance tests pin `Session Cost: $0.0000` for turn 1 by design, because telemetry is emitted before the completion).
- [x] Sandbox proof: a replica adapter preferring `upstream_inference_cost` when positive yields `$0.0061` for the BYOK shape while preserving the reported fee for non-BYOK and for shapes without `cost_details`.
- [x] New defect candidate (explained, not fixed here): a failed recompute renders a confident `$0.0000` when the displayed identity has catalog pricing (MRE 01 case 5b). It is unreachable on the OpenRouter BYOK path, where a reported cost always exists, and fixing it would touch `PlanningService._display_telemetry` — a second production file, outside this session's single-file scope. Recorded for a follow-up case.

### Investigation History
1. Traced the cost chain statically across the adapter, `PlanningService`, `SessionService`, and the telemetry formatter; observed that every link of the recorded-cost signal is live and that telemetry is emitted before the completion; concluded that the remaining explanations are provider-reported-zero semantics and pre-response display ordering.
2. Read slice 00-11's operational notes; observed that the display gate was intentionally relaxed to key off an explicit recorded flag rather than `cost > 0`; concluded that a recorded free-model zero and a genuinely unpriced model are distinguishable only by that flag, so a zero under BYOK means the adapter considered `0.0` a real price.
3. Built and ran the hermetic response-shape MRE against the real adapter and telemetry; observed cases 1/3 print the reported figure, case 2 prints `$0.0000` by design, case 4 prints `$0.0000` for a recorded free price, case 7 prints `$???`, and case 5b prints a confident `$0.0000` for a failed recompute; concluded that a real reported price is never masked, that the OpenRouter BYOK zero must be the provider's own `usage.cost`, and that case 5b is a separate masked-failure defect.
4. Verified that litellm's `_response_cost_calculator` prefers the OpenRouter header (so a reported fee always wins) and that the `Usage` pydantic model has `extra: allow`, so `usage.cost` and `usage.cost_details` are preserved on the response; concluded that an adapter-level read of `upstream_inference_cost` is feasible.
5. Ran a sandbox replica (`spikes/debug/session-cost-zero-byok/replica_litellm_adapter.py` + `02-openrouter-byok-fix-proof.py`) that prefers `usage.cost_details.upstream_inference_cost` when positive and adds any reported fee; observed the BYOK shape yields `$0.0061` and the non-BYOK shape keeps `$0.0105`; concluded that the fix is a small, self-contained change to `LiteLLMAdapter._reported_cost` and stays regression-free.
6. Applied the fix to production, splitting `_reported_cost` into `_upstream_inference_cost`, a summed-fee path, and the unchanged `_hidden_reported_cost`; observed all 18 existing telemetry tests still pass and MRE 01's verdict table is byte-identical; concluded the refactor is regression-free and every non-BYOK and native-provider response is untouched.
7. Added three regression tests (waived-fee preference, spend-plus-fee summation, and an eight-case matrix covering absent usage, absent/`None`/non-dict `cost_details`, absent key, zero, `None`, and non-finite upstream); observed 28 pass in the telemetry file and `make test` green at 2218 passed, 5 skipped; concluded the BYOK behavior is now pinned against silent reversion.
8. Audited the blast radius by grepping every `get_completion_cost` and `_reported_cost` reference; observed the only production caller is `PlanningService._perform_generation_with_retry` and every other reference is a test double or harness mock; concluded the change is confined to one adapter file plus one test file, with the cumulative telemetry and the `max_session_cost` guardrail improving as a side effect rather than needing migration.

9. Verified post-push CI attribution by comparing per-job conclusions across the five most recent `main` runs. Observed `Quality Checks` as the only job with conclusion `failure` on fix commit `2027b8e1` and on base `f93c6bf3` (the documented nine-step non-blocking baseline), `Test Suite (ubuntu-latest)` and `Test Suite (windows-latest)` `success`, and `Test Suite (macos-latest)` `cancelled` on four of the five runs including the base. The macOS check-run annotation reads "The job was not acquired by Runner of type hosted even after multiple attempts" with macOS arm64 capacity notices and an empty step table, so the leg never executed a single step. Concluded that the blocking matrix carries no regression signal from this fix, and recorded the runner-capacity cap as Milestone 5 debt.

## Solution
### Root Cause
The adapter trusted the only cost figure it could see. litellm mirrors OpenRouter's `usage.cost` into `_hidden_params` — first as `response_cost`, then through the `llm_provider-x-litellm-response-cost` header — and `LiteLLMAdapter._reported_cost` read exactly that. Under BYOK, `usage.cost` is OpenRouter's own fee: 5% of list price, waived while the monthly free allowance lasts, so it is frequently `0.0`. The adapter therefore returned a real, trusted `0.0`, marked the response as recorded, and the cumulative session cost never rose. The user's actual spend is `usage.cost_details.upstream_inference_cost`, which litellm preserves verbatim on `response.usage` and which no code path ever read.

The gap is an omission, not a code regression: the reported-cost precedence introduced by slice 00-11 made any reported figure authoritative, which converted a pre-existing blindness into a confident zero. The design assumption behind it is written down in that slice — the hydrator deliberately carries "no per-upstream-provider price because the reported cost is the source of truth" — and that assumption does not hold for BYOK.

Fixed directly in production code (one file): `LiteLLMAdapter._reported_cost` now prefers a positive `usage.cost_details.upstream_inference_cost`, adds any reported fee on top, and otherwise falls back to the unchanged hidden-params read. The upstream read is guarded by `isinstance(details, dict)` so an auto-specced `Mock` usage is never mistaken for real spend, and a non-finite value is treated as absent through the existing `_finite_cost`.

Evidence: [`spikes/debug/session-cost-zero-byok/01-openrouter-byok-cost-display-mre.py`](/spikes/debug/session-cost-zero-byok/01-openrouter-byok-cost-display-mre.py) produced the eight-shape verdict table in the Causal Model; [`spikes/debug/session-cost-zero-byok/02-openrouter-byok-fix-proof.py`](/spikes/debug/session-cost-zero-byok/02-openrouter-byok-fix-proof.py) drove [`replica_litellm_adapter.py`](/spikes/debug/session-cost-zero-byok/replica_litellm_adapter.py) to `ALL PASS` (BYOK `0.0061`, non-BYOK `0.0105`, no-`cost_details` `0.0021`). The regression pin lives in [`test_litellm_adapter_telemetry.py`](/tests/suites/unit/adapters/outbound/test_litellm_adapter_telemetry.py); `make test` reports 2218 passed, 5 skipped.

The first-turn `$0.0000` is not part of the root cause: telemetry is emitted from `_run_planning_phase` before the completion call, so the panel always shows the inherited cumulative cost, and acceptance tests pin that behavior deliberately.

### Affected Components
- `LiteLLMAdapter` ([`litellm_adapter.py`](/src/teddy_executor/adapters/outbound/litellm_adapter.py)): fixed. `_reported_cost` became a three-tier read with two new private helpers, `_upstream_inference_cost` and `_hidden_reported_cost`. The `get_completion_cost` signature, the `cost_never_raises` invariant, the hydration retry, the tiered diagnostics, and the `_teddy_cost_recorded` marking are unchanged.
- `PlanningService._perform_generation_with_retry` ([`planning_service.py`](/src/teddy_executor/core/services/planning_service.py)): unchanged. It is the only production consumer of `get_completion_cost`, and its per-turn `turn_cost` now carries real BYOK spend, which flows to console telemetry, `meta["turn_cost"]`, and the loop guard.
- `SessionService._persist_next_meta` ([`session_service.py`](/src/teddy_executor/core/services/session_service.py)): unchanged. It accumulates the corrected `turn_cost` into `cumulative_cost`, so the panel now rises across turns on BYOK.
- `SessionLoopGuard` ([`session_loop_guard.py`](/src/teddy_executor/core/services/session_loop_guard.py)): unchanged. `max_session_cost` now measures real spend under BYOK instead of accumulating `0.0`.
- `test_litellm_adapter_telemetry.py`: three regression tests added, 28 tests in the file.
- `litellm_adapter.md` component doc: invariant, `get_completion_cost` postconditions, and a new BYOK cost accounting subsection updated in this turn.
- `PlanningService._display_telemetry`: out of scope. The MRE 01 case 5b display-gate defect (a confident `$0.0000` for a failed recompute when the displayed identity is priced) is documented above for a follow-up case, because fixing it requires a second production file.
