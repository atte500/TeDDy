# Component Design: ProjectContext
- **Status:** Refactoring
- **Classification:** Core Domain
- **Source:** [`src/teddy_executor/core/domain/models/project_context.py`](/src/teddy_executor/core/domain/models/project_context.py)

## Purpose
Represents the complete, aggregated project context gathered by the `ContextService`. It is the return type of the `IGetContextUseCase` inbound port and the data structure every context-presenting adapter consumes.

## Consumers
- [`IGetContextUseCase`](../ports/inbound/get_context_use_case.md): Declares `ProjectContext` as its return type.
- [`IRunPlanUseCase`](../ports/inbound/run_plan_use_case.md): Carries the context into plan execution.
- [`IPlanReviewer`](../ports/inbound/plan_reviewer.md): Displays context metadata during review.
- [`ContextService`](../services/context_service.md): Builds the `ProjectContext` instance.
- [`PlanningService`](../services/planning_service.md): Consumes the context to assemble the LLM prompt.
- [`SessionPruningService`](../services/session_pruning_service.md): Reads `ContextItem` metadata to prune context.
- [TextualPlanReviewer](../../adapters/inbound/textual_plan_reviewer.md): Renders context items in the TUI.

## Dependencies
None — this is a passive data structure.

## Class Invariants
- `mutable_dataclasses`: `ProjectContext` and `ContextItem` are standard (non-frozen) dataclasses; `ContextItem.selected` is mutated by the reviewer to reflect per-turn selection.
- `field_defaults`: `selected` defaults to `True`; `agent_name` defaults to `"Unknown"`; `model_name` defaults to `"Unknown"`; the integer token counters default to `0`; `session_root` defaults to `None`; `session_cost` defaults to `None`.
- `cost_absence_is_not_zero`: `session_cost` is `Optional[float]` so unrecorded spend (`None`) and recorded free spend (`0.0`) stay distinguishable facts; every renderer routes through `format_cost_usd`, which renders `None` as `$???` and any recorded amount at exactly four decimal places.
- `model_name_is_authoritative`: `model_name` carries the effective model resolved at the composition root, so the panel reports the model that will actually answer rather than the global default; the provider is derived from it by `split_model_identity` instead of being stored, because a LiteLLM provider prefix is optional and a stored copy could disagree with the name it was derived from.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
None — this is a passive data structure.

## Data Contracts
- **`ContextItem`** (dataclass): `path: str`, `token_count: int`, `git_status: str`, `scope: str`, `selected: bool = True`, `auto_prune_reason: Optional[str] = None`.
- **`ProjectContext`** (dataclass): `header: str`, `content: str`, `scoped_paths: Dict[str, List[str]] = {}`, `git_status: Optional[str] = None`, `items: List[ContextItem] = []`, `agent_name: str = "Unknown"`, `system_prompt_tokens: int = 0`, `content_tokens: int = 0`, `total_window: int = 0`, `session_root: Optional[str] = None`, `model_name: str = "Unknown"`, `session_cost: Optional[float] = None`.
- **`git_status` field:** Holds the `git status --porcelain -b` output. It drives the fenced Markdown body and the item badge parser.
- **`session_root` field:** Names the session the context was assembled for, when one is in scope. `ContextService` sets it, and the TUI reads it to gate its Session/Turn/History grouping on the same discriminator the service used; `None` selects the session-agnostic legacy grouping.
- **`model_name` field** (slice 04-05): `str`, default `"Unknown"`. Carries the effective model resolved at the composition root — `--model`, then `agents.<persona>.model`, then `llm.model` — so the reviewer's Model row names the answerer. An unresolved model renders `Unknown`, never an empty cell. Provider is deliberately not a field: `split_model_identity` derives it, because the prefix segment is optional.
- **`session_cost` field** (slice 04-05): `Optional[float]`, default `None`. Carries the turn's accumulated figure as `resolve_session_cost` decided it from the producer's own `meta.yaml` — the recorded-cost signal or a priced model, never `cumulative_cost > 0` — and only a session supplies one, because no ledger exists outside a session, so `None` outside a session reads as unrecorded rather than as a zero. Both fields arrive as additive keywords on the existing `get_context` seam, which already carries its `PLR0913` seam annotation for exactly this reason. `ISessionManager.get_cumulative_cost` is not this field's source: it seeds the guardrail baseline at run start.

## Operations
None — this component holds data only.
