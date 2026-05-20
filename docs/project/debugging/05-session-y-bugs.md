# Bug: Session -y Bugs

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-04-context-management-ui](../slices/00-04-context-management-ui.md)
- **Specs:** [context-management-ui](../specs/context-management-ui.md)

## Symptoms

When running the `teddy` CLI session commands (`start` or `resume`) in non-interactive / auto-approve mode (`-y` / `--yes`), the following three bugs occur:
1. **Auto-prune logic does not apply:** Files that are meant to be auto-pruned (e.g., failed validation reports/plans, deleted files, or exceeding context token budget) are never pruned from the filesystem context.
2. **Missing Start Prompt:** Running `teddy start` with `-y` does not prompt the user for the initial message if one was not provided via `-m`, leaving the session with a blank/None initial request.
3. **Premature Loop Exit:** The multi-turn session loop immediately terminates and exits after only one turn is completed, rather than continuing to execute subsequent turns up to the `SessionLoopGuard` limit.

## Context & Scope

### Regressing Delta
The bug was introduced during the implementation of Slice 4 & 5 (Core Session, Context Engine, and Plan Validation) when adding interactive/non-interactive logic paths.

### Environmental Triggers
No special OS-specific triggers; occurs on all platforms when invoking `teddy start` or `teddy resume` with the `-y` / `--yes` flag.

### Ruled Out
- `SessionPruningService` core pruning rules (they work correctly when invoked).
- `SessionService` transition logic (correctly deletes files if `pruned_paths` is provided).

## Diagnostic Analysis

### Causal Model

1. **Auto-Pruning Skip:**
   In `SessionOrchestrator.execute`, resolving the `project_context` and calling the `SessionPruningService.prune` method is wrapped inside an `interactive` guard:
   ```python
   if is_session and plan_path and not project_context and interactive:
   ```
   When running with `-y`, `interactive` is `False`, skipping context resolution and auto-pruning. Furthermore, even if `project_context` were pruned, the unselected items are never harvested into `plan.metadata["pruned_context"]` programmatically (which only happens via the TUI's submit action).

2. **Start Prompt Skip:**
   In `session_cli_handlers.py:handle_new_session`, prompting for the initial message is guarded by `interactive`:
   ```python
   if message is None and interactive:
       message = user_interactor.ask_question("What are we working on?")
   ```
   When `interactive` is `False`, the user is never prompted and the session starts with `message = None`.

3. **Loop Exit:**
   In both `handle_new_session` and `handle_resume_session` (inside `session_cli_handlers.py`), the while-loop break condition contains a `not interactive` check:
   ```python
   if not interactive or not loop_guard.should_continue(turn_count):
       break
   ```
   When `interactive` is `False`, `not interactive` is `True`, immediately breaking the loop after the first turn.

### Discrepancies
- None.

### Investigation History
1. Checked CLI handlers and main orchestrator references to `yes` / `interactive`. Identified direct code guards for all three symptoms. (resolved: Verified programmatically using custom mock tests)
2. Created replica shadow files and verified fixes in the sandbox environment. (resolved: All three MRE tests passed successfully with code 0)

## Solution

### Root Cause
1. **Auto-Pruning Bug:** In `SessionOrchestrator.execute`, resolving and auto-pruning `project_context` was guarded by `interactive`, meaning that in `-y` mode, no auto-pruning occurred. Furthermore, because the TUI was skipped, unselected items from `project_context` were never programmatically harvested into `plan.metadata["pruned_context"]`, preventing physical deletion on turn transition.
2. **Missing Prompt Bug:** In `session_cli_handlers.py:handle_new_session`, asking for the initial request message was guarded by `interactive`, preventing any start prompt when running with `-y` unless `-m` was provided.
3. **Loop Breakout Bug:** In both `handle_new_session` and `handle_resume_session` (in `session_cli_handlers.py`), the while-loop termination checked `if not interactive`, forcing an exit after turn 1 when `-y` was provided.

### Verified Fix
1. **Always Auto-Prune:** Remove the `interactive` guard from the `project_context` block in `SessionOrchestrator.execute`, so that auto-pruning is always applied in session mode.
2. **Programmatic Harvest:** In `SessionOrchestrator.execute`, if `interactive` is False, programmatically harvest unselected paths from `project_context.items` into `plan.metadata["pruned_context"]` so they get processed by `finalize_turn`.
3. **Always Prompt for Missing Start Message:** In `handle_new_session`, remove the `interactive` guard from the message resolution block so the user is always prompted if they do not provide a message via `-m`.
4. **Iterative Session Loop:** In the session execution handlers, remove `not interactive` from the while-loop break condition, allowing loop continuation up to the configured `SessionLoopGuard` maximum turns.
