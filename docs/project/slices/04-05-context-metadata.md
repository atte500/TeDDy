# Slice: Model, Provider, and Session Cost in the Context Panel
- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [ProjectContext](/docs/architecture/core/domain/project_context.md), [ContextService](/docs/architecture/core/services/context_service.md), [PlanningService](/docs/architecture/core/services/planning_service.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md), [SessionLoopGuard](/docs/architecture/core/services/session_loop_guard.md), [Money](/docs/architecture/core/utils/money.md), [Model Identity](/docs/architecture/core/utils/model_identity.md)
- **Scope Slug:** `context-metadata`

## Goal
Let a reviewer see which model is answering and what the session has cost before approving a plan, and render every cost display at exactly four decimal places so the panel, the terminal telemetry, and the guardrail notice never disagree.

## Context
- `populate_context_detail` (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`): The aggregate branch renders `Total Context`, `System`, `Session`, `Turn`, and `History` token rows for the Context root and every scope label. It renders no model, provider, or cost row.
- `ProjectContext` (`src/teddy_executor/core/domain/models/project_context.py`): Carries `agent_name`, `system_prompt_tokens`, `content_tokens`, `total_window`, and `session_root`. `agent_name` and `total_window` are the precedent that session and model metadata ride on this DTO rather than arriving through a new constructor argument.
- `IGetContextUseCase.get_context` and `ContextService.get_context`: Already take additive keywords (`agent_name`, `system_prompt_tokens`, `total_window`), each annotated `# noqa: PLR0913 - inbound-port seam; additive keywords`, so extending the seam further is the established pattern.
- `PlanningService` (`src/teddy_executor/core/services/planning_service.py`): Renders the terminal Session Cost line as `f"${cumulative_cost:.4f}"`, with a `$???` fallback selected by the explicit `cost_recorded` signal rather than by `cost > 0`.
- `ProductionSessionLoopGuard.should_continue`: Renders the cost-limit notice with `f"${cost_delta:.2f}/${max_cost:.2f}"`, a second, independently written money format.
- Reviewer producers: The panel receives the `ProjectContext` that `PlanningService.generate_plan` returns alongside its plan, with `SessionOrchestrator._gather_fallback_context` covering a resumed PENDING_PLAN turn. Both already resolve the effective model and hold the turn's metadata a few lines above their `get_context` call. The third caller, `session_cli_handlers.handle_context_command`, is the `context` export path and never reaches the reviewer.
- Recorded-cost signal: `PlanningService` writes `meta["cost_recorded"] = True` when the adapter priced the turn, and `SessionService._persist_next_meta` carries both `cumulative_cost` and `cost_recorded` into every later turn, so a turn's own `meta.yaml` already answers "what has this session cost, and was that figure recorded?" without a ledger lookup.
- Effective model resolution: The composition root resolves flag → `agents.<persona>.model` → `llm.model` and already hands the result to the startup banner, so the value exists before the first turn. `ContextService.get_context` receives that same value as its existing `model` keyword for token counting, so the model row derives from it rather than from a second keyword that must be kept in agreement.
- Legal provider form: A LiteLLM model string is `provider/model`, where the provider segment is optional, so provider is a pure function of the resolved model name and needs no adapter call.
- `docs/project/specs/interactive-session-workflow.md`, Console & TUI Polish: Fixes the requirement — the Context root displays the current model name and the cumulative session cost at exactly four decimal places, with the same precision across every display.

## Scenarios

> As a reviewer, I want to know the model and the spend before I approve a plan.

```gherkin
Given a session whose effective model is openrouter/~deepseek/deepseek-flash-latest and whose accumulated cost is 0.42
When I highlight the Context root
Then the right panel shows Model, Provider, and Session Cost rows
And Session Cost reads $0.4200
```

> As a reviewer, I want the panel and the terminal to agree on every figure.

```gherkin
Given a cumulative cost of 1.234567
When the Context root and the terminal telemetry line both render it
Then both show $1.2346
```

> As a reviewer in a run with no recorded cost, I want an honest placeholder rather than a fabricated zero.

```gherkin
Given a turn whose metadata carries no recorded-cost signal
When the Context root renders the cost row
Then it reads $???
```

## Edge Cases
- **Stateless run**: If `project_context.session_root` is `None`, then the cost row reads `$???` while model and provider still render, because no cumulative ledger exists outside a session.
- **Unresolved model**: If the effective model resolves to nothing, then the Model row reads `Unknown` and Provider reads `unknown`, because the panel must never render an empty cell and the splitter never invents a provider.
- **Trailing zeros**: If the cost is exactly `0.10`, then it renders `$0.1000`, because fixed four-decimal rendering is what makes two figures comparable at a glance.
- **Recorded zero**: If a free provider records `0.0`, then it renders `$0.0000`, because recorded zero and unrecorded cost are different facts.
- **Provider-less model**: If the model string carries no `/`, then provider reads `unknown`, because LiteLLM provider prefixes are optional.
- **Large amount**: If the cost exceeds one thousand dollars, then no thousands separator is added, because the guardrail notice must stay greppable with the same format.
- **Below display precision**: If the cost is `0.00004`, then it renders `$0.0000`, because four decimals is the standard and the ledger keeps the remainder for the turns that follow.

## Key Unknowns
- [x] [Domain] Provider derivation: settled on the prefix rule. `LiteLLMAdapter._provider_resolution_errors` rejects a model without a provider prefix and tells the user to prefix `llm.model`, and litellm resolves the provider from that same string, so the provider is local knowledge rather than adapter state. `ProjectContext` therefore gains `model_name` only and the reviewer splits it with the pure `split_model_identity` helper; a prefix-less model resolves to provider `unknown`.

## Impact
1. `[EXTEND]` `ProjectContext` — add `model_name: str = "Unknown"` and `session_cost: Optional[float] = None`, where `None` means unrecorded and `0.0` means recorded zero. Both are appended and defaulted, so every existing construction stays valid.
2. `[EXTEND]` `IGetContextUseCase.get_context` and `ContextService.get_context` — add the additive `session_cost: Optional[float] = None` keyword under the existing seam annotation, and populate `model_name` from the existing `model` keyword (blank resolves to `Unknown`) instead of adding a second model keyword that must stay in step with it.
3. `[NEW]` `format_cost_usd` and `resolve_session_cost` in `src/teddy_executor/core/utils/money.py` — the one money formatter (exactly four decimals, `$???` for `None`) and the one recorded-cost decision (`cumulative_cost` when the turn recorded a cost or the provider prices the model, else `None`), so the panel and the terminal cannot answer differently.
4. `[NEW]` `split_model_identity` in `src/teddy_executor/core/utils/model_identity.py` — a pure `(name, provider)` splitter used by the panel.
5. `[MIGRATE]` `PlanningService.generate_plan` and `SessionOrchestrator._gather_fallback_context` — pass `session_cost=resolve_session_cost(meta, llm_client.supports_pricing(model=model))` into `get_context`.
6. `[MIGRATE]` `textual_plan_reviewer_helpers.populate_context_detail` — render the Model, Provider, and Session Cost rows in the aggregate branch.
7. `[MIGRATE]` `PlanningService` Session Cost line and `ProductionSessionLoopGuard` cost notice — both go through `format_cost_usd`, removing the two other money formats.
8. `[MIGRATE]` The `ProjectContext`, `ContextService`, `PlanningService`, and reviewer component pages, plus the Ubiquitous Language entry for the shared formatter.

## Deliverables
- [x] **Interface** — Extend `ProjectContext` with `model_name` and `session_cost`, thread `session_cost` as an additive keyword through `IGetContextUseCase.get_context` and `ContextService.get_context`, and derive `model_name` from the existing `model` keyword; contract-test the defaults, the blank-model fallback, and the unrecorded-cost default without disturbing existing callers.
- [x] **Core** — Implement `format_cost_usd`, `resolve_session_cost`, and `split_model_identity` as pure functions with unit tests covering the four-decimal boundary, recorded zero, unrecorded cost, a provider-less model, and a nested provider segment.
- [x] **Harness** — Extend `ContextScenario` with `model` and `session_cost` fields, a canonical costed bundle, and a forwarding `get_context_kwargs`, migrating the pinned contract test to the widened dict.
- [x] **Wiring** — Resolve the session cost in `PlanningService.generate_plan` and `SessionOrchestrator._gather_fallback_context`, pass it into `get_context`, then render the Model, Provider, and Session Cost rows in `populate_context_detail` to complete the tracer bullet.
- [x] **Migration** — Route the terminal Session Cost line and the guardrail cost notice through `format_cost_usd`, and update any assertion pinned to the superseded format.
- [x] **Cleanup** — Update the four affected component pages and record `format_cost_usd` in the Ubiquitous Language as the one cost renderer.

## Implementation Notes

### Interface
- `ProjectContext` gained `model_name: str = "Unknown"` and `session_cost: Optional[float] = None`, appended after `session_root` so every existing construction kept its positional and default shape. The full unfiltered suite (2634 passed, 5 skipped) confirmed no construction or `replace()` caller broke.
- The seam gained exactly one keyword, `session_cost`. `ContextService.get_context` derives `model_name` from the `model` keyword it already receives for token counting (`(str(model).strip() if model else "") or "Unknown"`), so the displayed model and the counted model cannot diverge and no second model keyword needs keeping in step.
- The `None`-versus-`0.0` distinction is contractual at both the DTO and the seam: `None` means no figure was recorded (the panel renders `$???`), `0.0` is a recorded free-provider zero (it renders `$0.0000`). The dataclass docstring and the inbound-port docstring both state it, so a later producer cannot collapse the two.
- Tests landed in the two files that already own their contracts — `test_project_context.py` for the DTO defaults, `test_context_service.py` for the seam — instead of a new module that would have duplicated the container-resolved `ContextService` fake assembly.
- The seam tests render through a new `_render_empty_workspace` helper that pins an empty workspace and passes `include_tokens=False`, so `_count_text_tokens` is never reached and the model assertions stay hermetic.
- Red was 8 targeted contract failures (two `AttributeError` on the new DTO fields, five `AttributeError` on `model_name` across the model-derivation cases including the three blank-model parameters, and the `TypeError` for the unexpected `session_cost` keyword) with the 34 pre-existing tests in those modules still green; Green returned all 42.

### Core
- Three pure functions landed as two new modules, following the surrounding `core/utils/` convention of one small module with its own unit module beside it: `money.py` (`format_cost_usd`, `resolve_session_cost`) and `model_identity.py` (`split_model_identity`). No pre-existing money or model helper existed to extend, so nothing was duplicated.
- **The window-conjunct split is a deliberate behavior change, not an oversight.** The terminal's current decision is `show_cost = context_window > 0 and (pricing_supported or cost_recorded)` — three conjuncts where the slice's rule names two. `resolve_session_cost` implements only recorded-or-priced, because folding the window gate in would make a priced model whose window could not be resolved render `$???` in the terminal and a figure in the panel, which is precisely the disagreement this slice removes. The Migration deliverable therefore drops the shadow conjunct at the call site and leaves the window gate on the Context line, where "tokens / window" is the thing being described.
- `resolve_session_cost` coerces the persisted amount through a private `_recorded_amount` helper that degrades an absent or unparseable value to `0.0`. This is parity, not leniency: `PlanningService` reads the same field through `_safe_float`, whose contract explicitly tolerates mocks and strings because turn metadata comes back from YAML. Without it, the Migration swap would turn a telemetry render into a `ValueError`. The *decision* whether a figure was recorded still rests solely on `cost_recorded`/pricing, so only the amount degrades.
- `format_cost_usd` keeps the plain float the ledger already stores rather than introducing a second decimal representation; four decimals is what absorbs float-accumulation noise (`1.2000000000000002` → `$1.2000`) below display precision.
- `split_model_identity` partitions on the **first** `/` only, so a nested provider segment (`openrouter/~deepseek/deepseek-flash-latest`) keeps its inner slash in the display name. A blank provider segment, a missing separator, or an empty remainder all resolve to `unknown` rather than inventing a provider, and an unresolved model returns the `("Unknown", "unknown")` placeholders so the panel never renders an empty cell.
- Red was two `ModuleNotFoundError` collection errors (zero tests collected), proving the contract was the modules' absence rather than a misarranged fixture. A second, deliberately provoked Red pinned the tolerance gap: `test_a_malformed_accumulated_total_reads_as_a_recorded_zero` failed with `ValueError: could not convert string to float: 'unavailable'` while the 12 other money cases stayed green. Green returned 18 cases; the unfiltered suite returned 2652 passed, 5 skipped.

### Harness
- `ContextScenario` gained `model: str | None = None` and `session_cost: float | None = None` as trailing `NamedTuple` defaults, so the three canonical bundles that already existed kept their construction unchanged and no consumer needed editing.
- `get_context_kwargs()` widened from two keys to four (`context_files`, `session_root`, `model`, `session_cost`). The load-bearing observation: this needed no consumer change, because the helper tracks the **seam**, not the caller. The one consumer (`test_context_service.py`) splats the dict into `get_context(**kwargs)`, and the Interface deliverable had already put both keywords on that seam, so the widened dict resolved against the real signature on the first run. That is the structural reason this shared-harness change is inert to the other ~2600 tests rather than merely untested by them.
- `COSTED_SESSION` derives its path lists from `MIXED_SCOPES.context_files` instead of restating the three literals, so the partition payload and the costed payload cannot drift apart, and it carries the slice's own Gherkin identity (`openrouter/~deepseek/deepseek-flash-latest` at `0.42`) so the Wiring deliverable can assert `$0.4200` against a bundle a reviewer recognizes from the slice's scenario text.
- The builder gained `model` and `session_cost` keywords and passes them through its single construction path rather than leaving `_replace` as an escape hatch, so the "both session-mode scope keys always present" invariant cannot be bypassed by post-construction mutation.
- Red was `ImportError: cannot import name 'COSTED_SESSION'` at collection with zero tests collected — the bundle's absence, not a misarranged assertion. Green returned 39 (8 harness cases, one renamed and one added, plus the 31 pre-existing context-service cases); the unfiltered suite returned 2653 passed, 5 skipped, one net new case above the post-Core baseline.
- The harness design page was corrected in this deliverable rather than deferred to Cleanup. It is outside the slice's `Impact` list, so the As-Built rule does not cover it, but the widened forwarding made its stated invariant ("forwards the scope mapping together with `session_root`") false at the moment it landed, and shipping notes about a widened contract beside a page denying it would be self-contradictory.
- The slice's third deliverable was written before the turn-26 discovery and named a nonexistent `ContextScenarios`; the identifier is corrected to `ContextScenario` as the row was marked complete.

### Wiring
- Both producers resolve the cost with the same expression, `resolve_session_cost(meta, self._llm_client.supports_pricing(model=model))`, passed as the `session_cost` keyword of their existing seam call. The asymmetry feared at turn 34 did not exist: `SessionOrchestrator` holds `self._llm_client` (line 220) and already calls `get_context_window` and `get_text_token_count` on it inside `_gather_fallback_context`, so neither site needed the `pricing_supported=False` shortcut and the panel and the terminal answer "was this recorded?" identically by construction rather than by convention.
- In `PlanningService` the cost is resolved **before** the completion runs, from the turn's own `meta`, which `_persist_next_meta` has already carried `cumulative_cost` and `cost_recorded` into. That is deliberate: the figure a reviewer sees before approving is what the session has spent up to this turn, not a post-hoc total for a turn that has not happened yet.
- The three rows append after `• History` inside the `elif app.project_context:` branch, unbulleted, because the `• ` prefix marks the token breakdown's sub-rows and the model identity is not one of them. `Model` and `Provider` come from `split_model_identity(app.project_context.model_name)` and `Session Cost` from `format_cost_usd(app.project_context.session_cost)`, both imported locally inside the function beside the existing `DetailItem` and `is_session_history_path` imports.
- The tracer bullet chain is producer kwargs → seam carry-through → panel render, all inside the unit suites that already own those components. The reviewer is driven by acceptance suites, but they exercise layout, navigation, and editing; the panel is a pure function of `ProjectContext` whose provenance is provable only at the producer seam, so a new acceptance journey would have restated the same three assertions behind a TUI mount without adding evidence.
- The orchestrator case pins only that `session_cost` is present in `gather_kwargs`. Its fixture's turn metadata comes from a service double rather than a real mapping, so the recorded-versus-unrecorded decision is not observable there honestly; that decision is pinned in `test_money.py` and, over a real meta dict, by the planning pin. The limitation is recorded rather than papered over with a test that proves less than it appears to.
- The planning pin expects `session_cost=0.0`, corroborated twice: the pricing double reports support and the ledger is empty, and the turn-36 captured telemetry for that same state already printed `• Session Cost: $0.0000`.
- Red was 4 failed / 46 passed for exactly the predicted reasons — two panel cases on a missing `DetailItem` key, `test_generate_plan` on an `assert_called_once_with` diff whose actual call lacked `session_cost`, and the orchestrator presence assertion — with every incumbent case in those modules green. Green returned 50 passed across the three modules, and the unfiltered suite returned 2655 passed, 5 skipped: the Harness baseline plus the two net new panel cases.
- Deliberately untouched at the time: the telemetry gate in `PlanningService._display_telemetry` (`context_window > 0 and (pricing_supported or cost_recorded)`), which the Migration deliverable below replaced.

### Migration
- `_display_telemetry` now asks `resolve_session_cost(meta, self._llm_client.supports_pricing(model=model))` and renders `format_cost_usd(session_cost)`. Four locals died together rather than being left as dead weight: `cumulative_cost`, `cost_recorded`, `show_cost`, and `cost_str`. The `context_window` local survives deliberately, because the `• Context:` line still renders `tokens / window` — a different fact from the money figure.
- **Dropping the shadow `context_window > 0` conjunct is the point of the deliverable, not collateral.** The old gate conflated "is the window known?" with "was a cost recorded?", so a priced model whose window could not be resolved rendered `$???` on the terminal while the panel rendered a real figure. `resolve_session_cost` answers only the recorded-or-priced question, and the window gate stays on the Context line where the window is the thing being described.
- The cached-percentage suffix re-gated from the removed `show_cost` to `session_cost is not None and session_cost > 0`, keeping its `> 0` conjunct on purpose: a recorded free-model zero is a real figure but claims no cache ratio, since there is no spend to attribute it to.
- The guard notice routes **both** interpolated amounts through the formatter — `format_cost_usd(cost_delta)` and `format_cost_usd(max_cost)` — because it reports this run's delta against the configured limit, not the session total. Four decimals keep the `delta/limit` ratio shape readable and greppable with no thousands separator, which is what the "Large amount" edge case exists to protect.
- The guard assertion was a re-pin, not an addition: `"$1.50/$1.50"` became `"$1.5000/$1.5000"` in `test_production_guard_stops_on_max_cost_non_interactive`, a case whose limit resolves to `1.50` and whose delta is exactly `1.50`. My turn-43 claim that no test pinned that format was wrong; the turn-46 read corrected it before any edit.
- One parametrized row was **added** to `test_cache_telemetry_display.py` (`priced-model-with-unresolved-window`: `cumulative_cost 0.05`, `context_window=0`, pricing supported, expecting `$0.0500` with no cache suffix). Every incumbent row passes `context_window=128000`, so no existing case exercised the branch the conjunct removal flips. The row lives in the module that already owns the telemetry contract rather than in a new behavioural file, because a changed gate needs its new branch pinned and nothing else about the feature changed.
- Red was exactly the two predicted observations: the guard pin failing against the superseded `:.2f` render, and the new row failing with `assert '$0.0500' in '[blue]• Session Cost:[/blue] [magenta]$???[/magenta]\n'`. Green returned 15 passed across the two modules.
- **The first unfiltered run failed at 1 failed / 2655 passed**, on `test_generate_plan_displays_sentinel_for_unknown_model_telemetry`. Fault Evaluation put it in Local Recovery: only a test file was implicated and the observed production behaviour is the one the slice mandates. Root cause was a masked premise rather than a defect — the case forced `get_context_window=0` and never stated `supports_pricing`, so the removed conjunct had been short-circuiting before the auto-specced double's truthy default was ever consulted, and `resolve_session_cost` then honestly reported a priced turn over an empty ledger as `$0.0000`.
- The fix states the premise the case always implied (`supports_pricing=False`) instead of re-pinning the assertion to `$0.0000`. An unknown model is unpriceable in production, so `$???` is the correct product answer, and re-pinning would have pinned a mock artefact. The case now separates its two sentinels: the zero window drives `1.0k / ??? tokens`, missing pricing drives `$???`.
- Recovering the premise rather than relaxing the harness is deliberate. Port doubles leaving boolean capabilities unset is the underlying hazard, but making `supports_pricing` default to `False` harness-wide reaches acceptance and integration journeys and is a separate concern; it is recorded as Milestone 07 debt instead of folded into this deliverable.
- Final state: `test_planning_service.py` 18 passed, and the unfiltered suite 2656 passed / 5 skipped — the Wiring baseline plus the net new telemetry row, with both pricing-gated `$???` pins and the acceptance telemetry pin unchanged.

### Cleanup
- Each of the five pages was wrong in a different way. `project_context.md` was missing both new fields from its dataclass list **and** attributed `session_cost` to `ISessionManager.get_cumulative_cost`; the attribution is corrected rather than re-worded, because that accessor seeds the guardrail baseline (`session_cli_handlers.py` passes it as `initial_cost`) and never touches the DTO. `context_service.md` lacked `session_cost` on the `get_context` signature and never stated how `model_name` is derived, so both are named and the derivation is pinned to the same `model` keyword the counter already receives — otherwise a later reader adds a second model keyword and reintroduces the divergence this slice removed. `planning_service.md` documented the superseded three-conjunct `display_gate` and a `cache_suffix_gate` keyed on `cumulative_cost > 0`. `session_loop_guard.md` described the four-decimal notice in future tense and pinned a `planning_service.py:287` line reference that would rot. `textual_plan_reviewer.md` already carried the right `cost_rows_share_one_format` invariant, but its `review` postcondition never named the three rows.
- **The two new `core/utils` modules have design pages, and the note this slice first wrote claiming otherwise was wrong.** `docs/architecture/core/utils/` already holds `io.md`, `message_renderer.md`, and `paths.md`, so the layer has a per-module page convention and the As-Built rule's "create one following the component design template and path conventions" applied to `Impact` items 3 and 4. `money.md` and `model_identity.md` were therefore created with `Status: Implemented` and linked from the Component Map's Hexagonal Core table, and the three consumer pages now link them from `Dependencies` instead of naming a bare module path. My earlier claim rested on a grep scoped to `ARCHITECTURE.md`, where the three older utils pages are indeed absent: that gap, and the missing pages for `core.utils.markdown` and `core.utils.editor_names`, are pre-existing and out of scope here, so both are filed as documentation debt in a planned milestone rather than fixed in this slice.
- The Ubiquitous Language gained **Session Cost** (the formatter plus the recorded-cost decision, and the `None`-versus-`0.0` distinction) and **Model Identity** (the effective model with its derived provider). The slice mandates the first; the second follows the hygiene rule that new domain vocabulary is registered where code, tests, and prose can agree on it. Both sit beside the existing terms rather than in Key Architectural Decisions, which already carried the `Money Rendering` law.
- The stale-reference sweep resolved into the same grep that drove the corrections, because this slice only added and renamed nothing. Two hits were deliberately left alone: `04-04-guardrail-defaults.md` still records that 04-05 owns `format_cost_usd`, which is now simply true, and this slice's own earlier notes describe the pre-migration gate in past tense, which is their purpose.
- Component `Status` fields were left untouched. Three of the five pages read `Refactoring` and milestone 04 still holds in-flight slices (04-06 touches the reviewer's roster), so flipping them to `Implemented` here would assert a completion this slice cannot observe. The As-Built rule's `Implemented` instruction governs pages a slice **creates**, and none was created.

## Verification
1. **Panel contents:**
   Run `uv run teddy start -m "plan a small refactor"` and highlight the Context root.
   Verify the right panel shows Model, Provider, and Session Cost rows beneath the token breakdown, with Provider echoing the `llm.model` prefix.
2. **Rounding agreement:**
   Complete a turn and compare the terminal `• Session Cost:` line with the panel row.
   Verify both display the identical `$X.YYYY` figure with four decimals.
3. **Unrecorded cost:**
   Point `llm.model` at an id litellm does not price (for example `openrouter/unknown-model`) and confirm the panel and the terminal both read `$???` rather than `$0.0000`.
   `uv run pytest tests/suites/unit/core/utils/test_money.py` exercises the same rule deterministically.
