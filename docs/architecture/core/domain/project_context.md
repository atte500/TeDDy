# Component Design: ProjectContext
- **Status:** Implemented
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
- `field_defaults`: `selected` defaults to `True`; `agent_name` defaults to `"Unknown"`; the integer token counters default to `0`.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
None — this is a passive data structure.

## Data Contracts
- **`ContextItem`** (dataclass): `path: str`, `token_count: int`, `git_status: str`, `scope: str`, `selected: bool = True`, `auto_prune_reason: Optional[str] = None`.
- **`ProjectContext`** (dataclass): `header: str`, `content: str`, `scoped_paths: Dict[str, List[str]] = {}`, `git_status: Optional[str] = None`, `items: List[ContextItem] = []`, `agent_name: str = "Unknown"`, `system_prompt_tokens: int = 0`, `content_tokens: int = 0`, `total_window: int = 0`.

## Operations
None — this component holds data only.
