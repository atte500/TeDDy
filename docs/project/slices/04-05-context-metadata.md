# Slice: Model, Provider, and Session Cost in the Context Panel
- **Status:** Planned
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
- `ISessionManager.get_cumulative_cost(session_name) -> float`: Already exposes the session ledger the panel needs.
- Effective model resolution: The composition root resolves flag → `agents.<persona>.model` → `llm.model` and already hands the result to the startup banner, so the value exists before the first turn.
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
- **Unresolved model**: If the effective model resolves to nothing, then both model and provider read `Unknown`, because the panel must never render an empty cell.
- **Trailing zeros**: If the cost is exactly `0.10`, then it renders `$0.1000`, because fixed four-decimal rendering is what makes two figures comparable at a glance.
- **Recorded zero**: If a free provider records `0.0`, then it renders `$0.0000`, because recorded zero and unrecorded cost are different facts.
- **Provider-less model**: If the model string carries no `/`, then provider reads `unknown`, because LiteLLM provider prefixes are optional.
- **Large amount**: If the cost exceeds one thousand dollars, then no thousands separator is added, because the guardrail notice must stay greppable with the same format.
- **Below display precision**: If the cost is `0.00004`, then it renders `$0.0000`, because four decimals is the standard and the ledger keeps the remainder for the turns that follow.

## Key Unknowns
- [ ] [Domain] Provider derivation: should Provider show LiteLLM's own resolved provider, or the prefix segment of the model string computed locally? Design Sensitivity: if the prefix rule holds → the DTO gains only `model_name` and the reviewer splits it with a pure helper; if the resolved provider is required → `ProjectContext` gains a `provider` field and the composition root supplies it through the LLM adapter, making the panel depend on a call the reviewer cannot make today.

## Impact
1. `[EXTEND]` `ProjectContext` — add `model_name: str = "Unknown"` and `session_cost: Optional[float] = None`, where `None` means unrecorded and `0.0` means recorded zero.
2. `[EXTEND]` `IGetContextUseCase.get_context` and `ContextService.get_context` — add the matching additive keywords with the existing seam annotation.
3. `[NEW]` `format_cost_usd` in `src/teddy_executor/core/utils/money.py` — the single money formatter: exactly four decimal places, `$???` for `None`.
4. `[NEW]` `split_model_identity` in `src/teddy_executor/core/utils/model_identity.py` — a pure `(name, provider)` splitter used by the panel.
5. `[MIGRATE]` `session_cli_handlers.py` — pass the resolved model and `ISessionManager.get_cumulative_cost(session_name)` into `get_context`.
6. `[MIGRATE]` `textual_plan_reviewer_helpers.populate_context_detail` — render the Model, Provider, and Session Cost rows in the aggregate branch.
7. `[MIGRATE]` `PlanningService` Session Cost line and `ProductionSessionLoopGuard` cost notice — both go through `format_cost_usd`, removing the two other money formats.
8. `[MIGRATE]` The `ProjectContext`, `ContextService`, `PlanningService`, and reviewer component pages, plus the Ubiquitous Language entry for the shared formatter.

## Deliverables
- [ ] **Interface** — Extend `ProjectContext` with `model_name` and `session_cost`, and thread both as additive keywords through `IGetContextUseCase.get_context` and `ContextService.get_context` without disturbing existing callers.
- [ ] **Core** — Implement `format_cost_usd` and `split_model_identity` as pure functions with unit tests covering the four-decimal boundary, recorded zero, unrecorded cost, a provider-less model, and a nested provider segment.
- [ ] **Harness** — Extend `ContextScenarios` with a builder variant carrying a model name and a session cost so the panel branches are drivable without a real session.
- [ ] **Wiring** — Resolve the effective model and the cumulative cost in the start and resume handlers and pass them into `get_context`, then render the three rows in `populate_context_detail` to complete the tracer bullet.
- [ ] **Migration** — Route the terminal Session Cost line and the guardrail cost notice through `format_cost_usd`, and update their existing assertions to the shared format.
- [ ] **Cleanup** — Update the four affected component pages and record `format_cost_usd` in the Ubiquitous Language as the one cost renderer.

## Implementation Notes

## Verification
1. **Panel contents:**
   Run `uv run teddy start -m "plan a small refactor"` and highlight the Context root.
   Verify the right panel shows Model, Provider, and Session Cost rows beneath the token breakdown.
2. **Rounding agreement:**
   Complete a turn and compare the terminal Session Cost line with the panel row.
   Verify both display the identical `$X.YYYY` figure with four decimals.
3. **Unrecorded cost:**
   Run `uv run teddy execute --plan-content <plan>` outside a session.
   Verify the panel shows `$???` rather than `$0.00`.
