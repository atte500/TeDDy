- **Status:** Refactoring

## Purpose / Responsibility
Reduces context size by deselecting irrelevant or failed turns from `turn.context`.

## Implementation Details / Logic
### Successful Message-Turn Exception
1. When scanning turns for pruning:
2. Read the `plan.md` for each turn.
3. If the plan contains a `## Message` section AND the `status` is Green (no 🔴/🟡 in status line):
4. **EXCEPTION**: This turn is immune to pruning based on retention limits or context budget. This preserves conversational thread continuity.

## Failure Modes
- **Mis-scoped Threshold Summation**: If `_apply_global_budget` sums items from ALL scopes (Session, System, Turn) instead of ONLY Turn-scope items, Session-scope files (from `session.context`) and System prompts can inflate the total token count, triggering premature pruning of the working set.
- **Stale Config Key**: If the config key `global_context_threshold` is read instead of `turn_context_threshold`, users with updated configs may silently fall back to an incorrect key. Backward compatibility fallback mitigates this.
- **Zero/Negative Threshold**: If the threshold is set to 0 or negative, the method must be a no-op. Current implementation already handles this via the early return guard.

## Ports
- **Inbound**: Called by `prune()` method during `SessionPlanner`/`SessionOrchestrator` context preparation flow.
- **Outbound**: Reads `auto_pruning.turn_context_threshold` (with `global_context_threshold` fallback) from `IConfigService`.

## Implementation Details / Logic
### Global Budget Heuristic (`_apply_global_budget`)
The `_apply_global_budget` method enforces a total token budget for the Turn-scope working set. It is called as Heuristic 2 in the prune pipeline (after Retention Limit).

#### Current Behavior (Incorrect)
```python
total_tokens = system_prompt_tokens + sum(item.tokens for item in items if item.selected)
```
This sums ALL selected items (Session, System, and Turn scopes) plus system prompt tokens.

#### Required Behavior (Per Spec)
```python
total_tokens = sum(item.tokens for item in items if item.selected and item.scope == "Turn")
```
This sums ONLY Turn-scope items. Session-scope and System-scope items are excluded from the budget calculation, though they remain in the final payload.

#### Backward Compatibility
- Primary key: `auto_pruning.turn_context_threshold`
- Fallback key: `auto_pruning.global_context_threshold` (with deprecation warning via `logging.warning`)
- If neither key is set, threshold defaults to 0 (budget heuristic skipped)

### Successful Message-Turn Exception
When scanning turns for pruning:
1. Read the `plan.md` for each turn.
2. If the plan contains a `## Message` section AND the `status` is Green (no 🔴/🟡 in status line):
3. **EXCEPTION**: This turn is immune to pruning based on retention limits or context budget. This preserves conversational thread continuity.

## Data Contracts / Methods
### `prune(context: ProjectContext, current_status: Optional[str]) -> ProjectContext`
Applies heuristics to deselect items.

### `_apply_global_budget(items: Sequence[ContextItem], threshold: int, spared_ids: set[str]) -> list[ContextItem]`
Enforces the Turn-scope token budget by pruning the largest files.
- **Parameters**:
  - `items`: Full list of context items (mixed scopes).
  - `threshold`: Token budget from config (or 0 to skip).
  - `spared_ids`: Set of turn IDs to exempt from pruning.
- **Logic**:
  1. If `threshold <= 0`, return items unchanged.
  2. Calculate `total_tokens = sum(item.tokens for item in items if item.selected and item.scope == "Turn")`.
  3. If `total_tokens <= threshold`, return items unchanged.
  4. Sort Turn-scope items by token count descending, prune largest until under budget.
  5. Non-Turn-scope items are never pruned by this heuristic.
- **Note**: The `system_prompt_tokens` parameter has been removed as of Slice 02-07. Callers must no longer pass it.
