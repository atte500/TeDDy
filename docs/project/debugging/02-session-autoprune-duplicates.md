# Bug: Session Auto-pruning Duplicates and Persistence Failure

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [02-session-autoprune-duplicates](/docs/project/slices/02-session-autoprune-duplicates.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms

### Actual Behavior
When a session exceeds the global context token threshold during execution:
1. The `SessionPruningService` prunes too much context (deselecting almost all turn-scoped files).
2. The pruned files are not actually removed from `turn.context` on disk, meaning they remain in context for subsequent turns.
3. This leads to failures in subsequent turns as the AI attempts to interact with context files that it believes are present but are actually unselected/pruned, or vice-versa.

### Expected Behavior
1. The pruning service should only prune the minimum number of largest turn-scoped files necessary to bring the total selected token count below the global context threshold.
2. Standard workspace files should not be double-counted if they exist in both `session.context` and `turn.context`.
3. Files pruned (either automatically or manually) must be correctly saved and removed from `turn.context` on disk, in both interactive and non-interactive modes, and during automated replan flows.

## Context & Scope

### Regressing Delta
The bug resides in the interaction between:
1. `ContextService._collect_items` (under-deduplication of files listed in both session and turn scopes).
2. `SessionOrchestrator.execute` (context harvesting only enabled in non-interactive mode).
3. `SessionLifecycleManager.trigger_replan` (failing to pass the `plan` parameter to `finalize_turn`).

### Environmental Triggers
- High token count of files in context (triggering global budget pruning).
- Runs in interactive mode, or validation-triggered replans.

### Ruled Out
- Low-level file system adapter (reading/writing `turn.context` is proven to work if correct pruned paths are provided).

## Diagnostic Analysis

### Causal Model
1. **Context Collection (Duplication)**: `ContextService.get_context` iterates over scopes and appends paths directly. If a file is in both `session.context` and `turn.context`, it is appended multiple times to `ProjectContext.items`, each with its corresponding scope (e.g. "Session" and "Turn"). (Verified: MRE returned 3 items instead of 2).
2. **Double-Counting & Aggressive Pruning**: In `SessionPruningService._apply_global_budget`, the total token count is computed by summing `item.token_count` for all selected items. This double-counts duplicates, artificially inflating the total tokens. Since only "Turn" scope items are candidates for pruning, the duplicate "Session" scoped item remains selected and counts toward the budget, forcing the service to prune other valid "Turn" scoped files unnecessarily. (Verified: MRE incorrectly pruned turn-scoped `file_a.txt` when true unique count was under budget).
3. **Persistence Failure (Interactive Mode)**: `SessionOrchestrator` limits context harvesting to non-interactive mode via `_harvest_context_if_non_interactive`. When running interactively, auto-pruned paths are never harvested into `plan.metadata["pruned_context"]`, meaning they remain on disk for future turns. (Verified: MRE plan metadata remained empty in interactive mode).
4. **Persistence Failure (Replan Mode)**: When validation fails and a replan is triggered, `SessionLifecycleManager.trigger_replan` is invoked. However, it does not receive the `plan` object in its signature, and thus invokes `self.finalize_turn` without passing the `plan` parameter. As a result, `finalize_turn` cannot extract `pruned_context` and no pruned paths are passed to `transition_to_next_turn` for the replanned turn. (Verified: MRE showed `finalize_turn` called with `plan=None`).

### Discrepancies
- None. (All verified via MRE and fully resolved).
### Investigation History
1. Initial discovery of pruning service and lifecycle manager files via `git grep`.
2. Deep dive into `SessionPruningService._apply_global_budget` and `ContextService._collect_items` revealed duplicate items.
3. Trace of `SessionLifecycleManager.trigger_replan` revealed missing `plan` argument to `finalize_turn`.
4. Constructed a Minimal Reproducible Example (MRE) in `spikes/debug/02-session-autoprune-duplicates-mre.py` replicating all three failures.
5. Created shadow files with proposed fixes in `spikes/debug/` demonstrating 100% correct behavior under sandboxed testing.

## Solution

### Root Cause
1. **Deduplication Issue in Context Collection**: `ContextService._collect_items` was grouping items under scopes without deduplicating paths across scopes. If a file was specified in both `"Session"` and `"Turn"` context manifest files, it was added to the items list twice. This double-counted the token metrics, causing aggressive context pruning.
2. **Context Persistence in Interactive Mode**: `SessionOrchestrator` only harvested context and updated the next turn's manifests when running in non-interactive mode. In interactive mode, this step was bypassed, leaving pruned files on disk.
3. **Replan Propagation Defect**: `SessionLifecycleManager.trigger_replan` did not accept the `plan` parameter and passed `None` to `finalize_turn`, preventing the extraction and writing of `pruned_context` to the next turn's `turn.context`.

### Verified Fix
1. **Deduplication Logic**: Update `ContextService._collect_items` to deduplicate files by checking path uniqueness. When a file exists in multiple scopes, prioritize non-`Turn` scopes (e.g., `Session`) to prevent duplicate entry or incorrect scope association.
2. **Interactive Harvesting**: Ensure `SessionOrchestrator` performs context harvesting in both interactive and non-interactive modes so that `plan.metadata["pruned_context"]` is parsed and applied to `T_next/turn.context` on disk.
3. **Replan Finalize propagation**: Add optional `plan` parameter to `SessionLifecycleManager.trigger_replan` and pass it to `finalize_turn` so that pruned files are correctly processed and saved to the filesystem during replans.

### Preventative Measures
1. **Systemic Context Safety**: Add high-value unit tests asserting path uniqueness in `ContextService.get_context()`.
2. **Interactive Regression Guard**: Add regression tests verifying that files pruned during an interactive session are correctly deleted from the next turn's `turn.context` file.
