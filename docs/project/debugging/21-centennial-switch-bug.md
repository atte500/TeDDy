# Bug: Centennial Turn Switch Session Exists After First Turn

- **Status:** Resolved
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

When a session reaches turn 99 and the automated centennial switch migrates to a new continuation session (e.g., `name-2`), the first turn (01) of the new session incorrectly reports that a session already exists. The user may see a "session exists" error, or the session state may reflect the previous session's data instead of a fresh start.

From the initial session history, we observed:

```
[99] implement-history-log-per-task-brief | Waiting for developer to respond...
• Model: deepseek/deepseek-v4-flash-20260423
• Context: 76.9k / 1048.6k tokens
• Session Cost: $0.7840

EXECUTE - Resolve merge conflict by checking out the upstream (HEAD) version...

[01] implement-history-log-per-task-brief-2 | Waiting for developer to respond...
```

Turn 99 executed successfully (EXECUTE action completed), but the continuation session `implement-history-log-per-task-brief-2` shows `[01]` as its first turn. The symptom suggests that something about the new session's state is incorrect after the migration.

**Expected Behavior**: The new continuation session should behave exactly like a fresh session, starting with an empty turn 01 that is ready for planning and execution. No "session exists" errors should occur.

**Actual Behavior**: After the migration, the new session's first turn reports that a session already exists, or the `orchestrate_session_loop` fails to handle the new session correctly.

## Context & Scope

### Regressing Delta
The centennial migration logic is implemented in `SessionService._resolve_next_turn_path` (lines 443-446), which checks if the current turn directory is "99" and creates a continuation session. The relevant code:

```python
def _resolve_next_turn_path(self, cur_dir: Path) -> tuple[str, Path, bool]:
    if cur_dir.name == "99":
        new_name = self._calculate_continuation_name(cur_dir.parent.name)
        return "01", cur_dir.parent.parent / new_name, True
    next_id = f"{int(cur_dir.name) + 1:02d}"
    return next_id, cur_dir.parent, False
```

The migration also clones session artifacts via `_clone_session_artifacts`. The bug was likely introduced by a change in the session handling code. Recent commits include fixes for session context, user-request turns, model display, and meta.yaml handling (see git log).

### Environmental Triggers
- The bug occurs when a session reaches turn 99.
- The session must have completed turn 99 (report.md exists).
- The next `resume()` call triggers the centennial switch.
- The continuation session must not already exist on disk.

### Ruled Out
- Not related to plan parsing or validation logic.
- Not related to CLI argument handling.
- Not related to the LLM client or prompt management.

## Diagnostic Analysis

### Causal Model
The root cause is a missing `session_name` update in `_orchestrate_session_loop` (`session_cli_handlers.py`). The loop captures `session_name` once and passes it to `orchestrator.resume()` on every iteration. After a centennial migration inside `SessionLifecycleManager.resume()`:

1. The `COMPLETE_TURN` branch calls `transition_to_next_turn()`, which creates a continuation session (e.g., `name-2`) with turn `01`.
2. `_handle_planning_and_execution()` calls `trigger_new_plan()`, which generates `plan.md` in the continuation session's turn `01` and returns the new session name (`name-2`).
3. The plan is executed, producing a report and transitioning the continuation session's turn `01` to `COMPLETE_TURN`.

**The bug**: The new session name returned by `trigger_new_plan()` is used only locally inside `_handle_planning_and_execution()` for `get_session_state()`. It is NOT propagated back to the outer loop's `session_name` variable.

4. On the next loop iteration, `orchestrator.resume(session_name)` is called with the **old** session name.
5. The old session is still in `COMPLETE_TURN` (turn 99 still has `report.md`), so the lifecycle manager triggers another migration.
6. `_resolve_next_turn_path(cur_dir)` sees `cur_dir.name == "99"` and computes the same continuation name (`name-2`), which already exists.
7. `transition_to_next_turn()` re-creates turn `01` in the continuation session (with `mkdir(exist_ok=True)`), overwriting the previously cloned artifacts and context.
8. `_handle_planning_and_execution()` replans and re-executes the continuation session's turn `01`, overwriting the previous work.

This repeats on every loop iteration, causing the continuation session's first turn to be processed multiple times — each time resetting the turn context and generating a new plan. The outer loop never progresses past the old session's turn 99.

### Discrepancies
- `_orchestrate_session_loop` uses a fixed `session_name` parameter. After centennial migration inside `orchestrator.resume()`, the loop's next iteration calls `orchestrator.resume(session_name)` with the old session name, triggering a second migration which re-processes the same continuation session (re-creating `name-2/01`, not a `name-2-2` duplicate). (resolved: confirmed via shadow verification script `21-shadow-loop-fix.py` in Turn 18, which empirically demonstrated that the fixed loop (Test 2 — updating `session_name` after migration) correctly transitions to `PENDING_PLAN` for the continuation session, while the original bug (Test 1 — fixed `session_name`) re-processes the old `COMPLETE_TURN` session on every iteration.)

### Investigation History
1. *Code reading*. Read all relevant services (session_service, session_lifecycle_manager, session_orchestrator, session_planner, session_repository, session_cli_handlers). The migration logic appears structurally correct, but the interaction between `trigger_new_plan` (which returns session name) and `get_session_state` (which uses that name) is a potential source of error. *Conclusion*: Need an MRE to observe actual runtime behavior.

2. *MRE execution (Turn 9)*. Low-level MRE confirmed `SessionService.transition_to_next_turn()` works correctly at filesystem level: continuation session created with correct name, turn 01, EMPTY state, cloned artifacts, proper meta.yaml. *Conclusion*: Bug is not in transition logic itself.

3. *Probe execution - CWD resolution (Turn 14-15)*. Probes to test session resolution from different CWDs failed due to macOS symlink edge-case in `resolve_session_from_path`. This is a distraction unrelated to the core bug. *Conclusion*: Abandoned CWD resolution probes.

4. *Integration test gap analysis (Turn 16)*. Grep confirmed NO existing integration/acceptance test covers the full resume loop after centennial migration. The unit test `test_migration_99_to_01_does_not_put_prompt_in_turn_directory` only verifies file placement. The test `test_handle_resume_session_loops_multiple_turns_when_non_interactive` mocks `_orchestrate_session_loop`, bypassing the actual loop. *Conclusion*: Confirmed test gap, reinforcing the hypothesis that the outer loop bug is the root cause.

5. *Code tracing - outer loop hypothesis*. In `_orchestrate_session_loop` (session_cli_handlers.py line 32), `session_name` is captured once. After centennial migration inside `orchestrator.resume()`:
   - `SessionLifecycleManager.resume()` sees COMPLETE_TURN
   - Calls `transition_to_next_turn()` → creates continuation session (e.g., `name-2/01`)
   - Calls `_handle_planning_and_execution(next_turn_dir, ...)`
   - Which calls `SessionPlanner.trigger_new_plan(turn_dir)` → returns new session name (e.g., `name-2`)
   - But this returned name is used only locally for `get_session_state(new_name)` and then discarded
   - The outer loop's next iteration uses the old `session_name`, resolving to the old session (still COMPLETE_TURN)
   - This triggers a second migration, re-creating `name-2/01` (not a `name-2-2` duplicate — `_calculate_continuation_name` deterministically returns `name-2` from `name`)
   *Conclusion*: This is the root cause. The fix is to update `session_name` in the outer loop after each `orchestrator.resume()` call to reflect any migration.

6. *Shadow verification (Turn 18)*. Executed `spikes/debug/21-shadow-loop-fix.py` to empirically confirm the outer loop bug and the fix. Test 1 (original bug — fixed `session_name`): first iteration created continuation session, second iteration with old `session_name` still saw `COMPLETE_TURN` for the old session and triggered a second migration. Test 2 (fixed — updated `session_name` after migration): first iteration created continuation session and updated `session_name`, second iteration correctly saw `PENDING_PLAN` for the continuation session, proving no re-migration. *Conclusion*: Root cause confirmed. The shadow script absent any modification to `src/` provides empirical proof of both the bug and the fix.

## Solution

**Root Cause**: The `_orchestrate_session_loop` function in `session_cli_handlers.py` captures `session_name` once and never updates it. After a centennial migration inside `SessionLifecycleManager.resume()` creates a continuation session, the loop continues to pass the old session name to `orchestrator.resume()` on subsequent iterations. This causes the lifecycle manager to keep processing the old session's turn 99 (still in `COMPLETE_TURN`), repeatedly triggering the migration and re-processing the continuation session's turn 01.

**Fix**: Update `session_name` in the loop after each `orchestrator.resume()` call if a centennial migration occurred. There are several viable implementation approaches:

1. **Propagate from LifecycleManager**: Modify `SessionLifecycleManager.resume()` to return the actual session name used (which may differ from the input after migration) alongside the `ExecutionReport`. The outer loop updates `session_name` from this return value.

2. **Detect via State Check**: After each `resume()` call, check if the current `session_name` still has its latest turn at "99" (indicating the old session never progressed). If so, resolve the continuation session via `session_manager.get_latest_session_name()` and update `session_name`.

3. **Add to Report Metadata**: Include the executing session name in the `ExecutionReport` metadata (populated from the meta.yaml or the turn path), and have the loop extract and use it.

The shadow verification confirmed that approach 1 (updating `session_name` after migration) correctly causes the second loop iteration to see `PENDING_PLAN` for the continuation session, preventing further migration.

**Preventative Measures**:
- Add a dedicated integration test that exercises the full resume loop across the centennial boundary (turn 99 → continuation session → turn 01 → turn 02), verifying `session_name` correctly follows the continuation session through multiple iterations.
- The `SessionLifecycleManager._handle_planning_and_execution()` method already returns the new session name via `trigger_new_plan()` — this value must be propagated through `resume()` to the caller.

**Verified By**: [`spikes/debug/21-shadow-loop-fix.py`](/spikes/debug/21-shadow-loop-fix.py) — 2 tests passed, 0 failed. The shadow script empirically demonstrates both the bug (redundant processing with fixed `session_name`) and the fix (correct `PENDING_PLAN` state with updated `session_name`) without modifying any production code.
