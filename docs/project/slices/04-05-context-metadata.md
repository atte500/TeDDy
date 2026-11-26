# Slice: Model, Provider, and Session Cost in the Context Panel
- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [ProjectContext](/docs/architecture/core/domain/project_context.md), [ContextService](/docs/architecture/core/services/context_service.md), [PlanningService](/docs/architecture/core/services/planning_service.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md), [SessionLoopGuard](/docs/architecture/core/services/session_loop_guard.md)
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
- [ ] **Harness** — Extend `ContextScenarios` with `model` and `session_cost` fields, a canonical costed bundle, and a forwarding `get_context_kwargs`, migrating the pinned contract test to the widened dict.
- [ ] **Wiring** — Resolve the session cost in `PlanningService.generate_plan` and `SessionOrchestrator._gather_fallback_context`, pass it into `get_context`, then render the Model, Provider, and Session Cost rows in `populate_context_detail` to complete the tracer bullet.
- [ ] **Migration** — Route the terminal Session Cost line and the guardrail cost notice through `format_cost_usd`, and update any assertion pinned to the superseded format.
- [ ] **Cleanup** — Update the four affected component pages and record `format_cost_usd` in the Ubiquitous Language as the one cost renderer.

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
