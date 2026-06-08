- **Status:** Refactoring
- **Last Updated:** 2026-06-08

## Purpose / Responsibility
The `SessionPruningService` is responsible for applying configurable auto-pruning heuristics to session context items. It prunes or deselects context items based on failure status, retention limits, and token budgets, while sparing certain turns (e.g., user-message turns and successful message turns) from pruning.
Reduces context size by deselecting irrelevant or failed turns from `turn.context`.

## Implementation Details / Logic
### Heuristic 4: Validation Failure Pruning (Conditional)
As of Slice 02-13, Heuristic 4 is guarded by the same green-state check as Heuristic 3 (Recovery Cleanup). Validation-failed turns are **only** pruned when a subsequent valid (green) plan exists, either on disk (`is_latest_green`) or as the current turn's status (`is_currently_green`). During chains of consecutive validation failures with no green anchor, all validation failure turns remain visible in context to preserve the audit trail.

### Sparing Logic (Preserved Turns)

The pruning service spares two categories of turns from ALL pruning heuristics (retention limit, global budget, non-green recovery, validation failure):

#### 1. User-Request Turns (Slice 02-10)
Turns where the user provided an additional message during the review phase (via TUI 'm' key or message reply). These are identified by the `- **User Request:**` metadata line in the turn's `report.md` file.
- **Detection method**: `_check_report_has_user_request(path)` — reads the report file and matches `r"^- \*\*User Request:\*\*"` with `re.MULTILINE`.
- **Why on report not plan**: The `user_request` metadata is captured during execution (`execution_orchestrator.py`, `session_orchestrator.py`) and rendered into the report via `execution_report.md.j2`. The report is the canonical source of truth at pruning time.
- **Edge cases**: Empty value after `- **User Request:**` still spares the turn (the presence of the key itself indicates user interaction).

#### 2. Successful Message Turns (Pre-existing)
Turns with a `## Message` plan section AND a `SUCCESS` report status. Identified by `_check_plan_is_message(path)` + `_check_report_is_success(path)`.
- **Status**: Pre-existing behavior, preserved by Slice 02-10.
- **Detection**: Checks the `plan.md` for `^## Message` and the `report.md` for `- **Overall Status:** SUCCESS`.

#### Integration
Both sparing checks are performed in `_update_turn_metadata_from_item`, which collects turn IDs into a single `spared_turns` set. This set is then passed to `_apply_retention_limit` and `_apply_global_budget` to exempt those turns from pruning. Additionally, spared turns are explicitly removed from the `turns_to_prune` dictionary in `_identify_turns_to_prune` to prevent Heuristics 3 & 4 from pruning them.

## Failure Modes
- **Mis-scoped Threshold Summation**: If `_apply_global_budget` sums items from ALL scopes (Session, System, Turn) instead of ONLY Turn-scope items, Session-scope files (from `session.context`) and System prompts can inflate the total token count, triggering premature pruning of the working set.
- **Green-State Guard Gap**: If the green-state guard (`is_currently_green or is_latest_green`) is accidentally removed or bypassed, Heuristic 4 will revert to unconditional pruning. All pruning callers must ensure `current_status` is passed and `turn_statuses` is populated.
- **Zero/Negative Threshold**: If the threshold is set to 0 or negative, the method must be a no-op. Current implementation already handles this via the early return guard.
- **Missing Report File**: If a turn has a plan but no `report.md` (e.g., execution was aborted), `_check_report_has_user_request` returns `False` gracefully via `_safe_read` path existence check — no crash. Edge case validated in prototype.
- **Empty User Request Value**: If the `user_request` metadata line is present but the value is empty, the turn is still spared (the presence of the header itself indicates user interaction). This is the correct behavior — an empty user_request still represents a user action (e.g., a blank message submission).

## Ports
- **Inbound**: Called by `prune()` method during `SessionPlanner`/`SessionOrchestrator` context preparation flow.
- **Outbound**: Reads `auto_pruning.turn_context_threshold` from `IConfigService`.

## Implementation Details / Logic
### Global Budget Heuristic (`_apply_global_budget`)
The `_apply_global_budget` method enforces a total token budget for the Turn-scope working set. It is called as Heuristic 2 in the prune pipeline (after Retention Limit).

#### Current Behavior (Per Slice 02-07)
```python
total_tokens = sum(item.tokens for item in items if item.selected and item.scope == "Turn")
```
This sums ONLY Turn-scope items. Session-scope and System-scope items are excluded from the budget calculation, though they remain in the final payload. The `system_prompt_tokens` parameter has been removed.

#### Backward Compatibility
- `auto_pruning.turn_context_threshold` is the sole key. If not set, threshold defaults to 0 (budget heuristic skipped).

## Data Contracts / Methods
### `_check_report_has_user_request(path: str) -> bool`
Detects whether a report file contains user-interaction metadata.
- **Input**: Root-relative path to a `report.md` file.
- **Output**: `True` if the file contains `- **User Request:**` on its own line (via regex `r"^- \*\*User Request:\*\*"`, multiline mode); `False` if the file is missing, unreadable, or the pattern is absent.
- **Caching**: Uses `_safe_read` which is cached within a single `prune()` call.

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
