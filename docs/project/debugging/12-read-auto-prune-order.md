# Bug: READ action files are pruned by auto-prune when they should survive
- **Status:** Resolved
- **Milestone:** [N/A](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When a file is both READ (via a READ action) and also subject to auto-pruning in the same turn (because it was already present in the context), the file is removed for the next turn. Expected behavior: the READ should be applied after auto-pruning, so the file should survive.

## Context & Scope

### Regressing Delta
Not yet identified. Likely related to the auto-pruning logic introduced in `session_pruning_service.py` or the turn transition logic in `session_service.py`.

### Environmental Triggers
Any session mode execution where a file is both in the existing context and explicitly READ in the same turn.

### Ruled Out
None yet.

## Diagnostic Analysis

### Causal Model
The bug is caused by an inverted order of operations in `SessionService.transition_to_next_turn()` (session_service.py). The method:
1. Reads the current turn's context paths from `turn.context`.
2. Applies READ/CREATE/EDIT side-effects via `_apply_execution_effects()` — adding paths that were read/created/edited during execution.
3. Then applies auto-pruning via `pruned_paths.discard()` — removing files that should not carry forward.

This order means READ files are added to context (step 2), then immediately pruned (step 3) if they were also auto-pruned. The correct order should be: prune first (remove stale entries), then apply READ side-effects (re-add files that were explicitly read).

The pruned_paths originate from `SessionOrchestrator._harvest_context()` which collects items marked `selected=False` (by `SessionPruningService.prune()`), stores them in `plan.metadata["pruned_context"]`. The `SessionLifecycleManager.finalize_turn()` then extracts them and passes to `transition_to_next_turn()`.

### Discrepancies
1. The order of operations between READ action processing and auto-pruning appears inverted. (resolved: Verified by reading `transition_to_next_turn()` in `session_service.py` — `_apply_execution_effects()` runs BEFORE the `pruned_paths` discard loop.)

### Investigation History
1. Turn 1: Read all relevant source files (session_pruning_service.py, context_service.py, session_service.py, action_dispatcher.py). Discovered key code paths and grep for "prune" references. Conclusion: Order issue suspected in transition_to_next_turn.
2. Turn 2: Read session_orchestrator.py and session_lifecycle_manager.py to trace the full pruned_paths flow. Searched for existing tests. Re-read session_service.py transition_to_next_turn to confirm the inverted order. Conclusion: Bug confirmed — READs are added before pruning discards them.

## Solution

### Root Cause

In `transition_to_next_turn()` in `session_service.py`, the order of operations was:

1. Apply READ/CREATE/EDIT side-effects via `_apply_execution_effects()`
2. Discard pruned paths via `paths.discard()`

This meant files that were explicitly READ were added to the context, then immediately removed by the pruning step. The expected behavior is for pruning to happen first (removing stale entries), then for READ side-effects to be applied on top (re-adding files that were explicitly read).

### The Fix

Swap steps 1 and 2 so pruning happens first, then execution effects are applied. This is a 4-line relocation within `transition_to_next_turn()`.

### Preventative Measures

The pattern "add then remove" is isolated to this single method. To prevent this class of bug globally, we rely on:
- The existing test `test_transition_to_next_turn_applies_read_side_effects` in `test_session_service_transition.py`, which was updated to verify the correct order.
- Code review guideline: when manipulating sets/paths that flow between turns, the order should be "prune stale state FIRST, then apply new side-effects ON TOP".
