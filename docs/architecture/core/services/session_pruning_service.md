# Component Design: SessionPruningService
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/session_pruning_service.py`](/src/teddy_executor/core/services/session_pruning_service.py)

## Purpose
Applies configurable auto-pruning heuristics to session context items. It deselects context files by failure status, retention limit, and token budget so the turn context stays bounded, while sparing turns that carry user interaction or a successful message.

## Consumers
- [`SessionOrchestrator`](./session_orchestrator.md): Calls `prune` on every session turn before harvesting pruned paths.

## Dependencies
- [`IConfigService`](../ports/outbound/config_service.md): Supplies the `auto_pruning.*` settings.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Reads plan and report files during heuristic evaluation.
- **`normalize_resource_path`** (`teddy_executor.core.utils.paths`): Normalizes link-aware context paths for turn matching.

## Class Invariants
- `read_cache_scope`: `_read_cache` is cleared at the start of every `prune` call.
- `config_gate`: When `auto_pruning.enabled` is false, `prune` returns the context unchanged.
- `turn_scope_budget`: The global budget sums only selected items whose scope is `Turn`.
- `spared_turns_exempt`: User-request turns and successful message turns are exempt from every heuristic.
- `failure_transparency`: An unexpected error logs to stderr and returns the original context unchanged.

## Inbound Ports
None — the service is consumed directly by `SessionOrchestrator`.

## Outbound Ports
- **`IConfigService`** and **`IFileSystemManager`**: Consumed through their contracts; see Dependencies.

## Data Contracts
- **`ProjectContext`** and **`ContextItem`** (`teddy_executor.core.domain.models.project_context`): The pruned aggregate and its items.
- **Return value:** A `ProjectContext` whose items carry updated `selected` and `auto_prune_reason` fields.

## Operations

### `prune(context, current_status=None) -> ProjectContext`
- **Preconditions:** `context` is a `ProjectContext`; `current_status` is the current plan's status string when available.
- **Postconditions:** Returns a `ProjectContext` with deselected items annotated by `auto_prune_reason`. Heuristics run in order: failure-status pruning, retention limit, then the global Turn-scope budget.
- **Exceptions:** None — an internal error is logged and the original context is returned.

### Heuristics
- **Validation-failure pruning:** A validation-failed turn is pruned only when a later non-validation-failure report exists, either on disk or as the current status. Consecutive validation failures stay visible to preserve the audit trail.
- **Recovery cleanup:** Non-green turns are pruned once the current status is green or the latest on-disk turn is green.
- **Retention limit:** Turns older than `auto_pruning.max_turns_retention` are deselected.
- **Global budget:** When the selected Turn-scope token total exceeds `auto_pruning.turn_context_threshold`, the largest Turn-scope files are deselected first.

### Sparing rules
- **User-request turns:** A report containing `- **User Request:**` is spared from every heuristic.
- **Successful message turns:** A plan containing `## Message` combined with a `SUCCESS` report is spared.
