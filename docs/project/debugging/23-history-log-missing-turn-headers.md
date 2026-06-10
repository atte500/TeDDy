# Bug: Turn Headers and Metadata Missing from history.log
- **Status:** Unresolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [docs/project/slices/00-27-history-log-timing-fix.md](/docs/project/slices/00-27-history-log-timing-fix.md)
- **Specs:** [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md)

## Symptoms
- **Expected:** The `history.log` file in a session root should capture all console output, including turn transition headers (e.g., `[01] teddy-work-2 | Waiting for pathfinder to respond...`) and metadata lines (e.g., `• Model: ... • Context: ... • Session Cost: ...`).
- **Actual:** Only action log lines (from `logger.info()` via `ActionDispatcher`) are captured after the fix for bug 22. The turn headers and metadata lines printed during the planning phase are still missing from `history.log`.
- **Minimal Reproduction Steps:** Start a session, let the planner generate a plan and execute it. Check `history.log` after the first turn. Action logs are present (thanks to bug 22 fix) but the initial turn header and metadata block are absent.

## Context & Scope
### Regressing Delta
This is a design oversight of the original history.log implementation (slice 00-25). The Tee was installed inside `SessionOrchestrator.execute()`, but the planning phase (which prints the turn header and metadata) runs *before* `execute()` is called in `SessionLifecycleManager._handle_planning_and_execution()`. No single commit introduced this; it's a timing gap in the Tee installation placement.

### Environmental Triggers
- Always reproduces in session mode. The planning phase always runs before Tee installation.

### Ruled Out
- The Tee itself works correctly: if installed early enough, it captures all output (proven by the fact that action logs are captured after the bug 22 fix).
- The `Rich.Console(stderr=True).print()` used by `display_message` reads the current `sys.stderr` at call time, so it would go through the Tee if installed.
- Bug 22 (handler caching) has been fixed; this is a separate timing issue.

## Diagnostic Analysis
### Causal Model
1. `SessionLifecycleManager._handle_planning_and_execution()` calls `self._session_planner.trigger_new_plan(turn_dir)` first.
2. `trigger_new_plan` calls `PlanningService.generate_plan()`, which prints:
   - Turn header via `self._user_interactor.display_message(msg)` (line 39-40 of `planning_service.py`)
   - Three metadata lines via `_display_telemetry()` using `self._user_interactor.display_message()` (lines 204, 209, 219)
   - Validation retry message via `display_message` (line 154)
3. These are printed *before* the Tee is installed, going directly to the real `sys.stderr`.
4. Only after the planning completes does `orchestrator.execute()` run, which installs the Tee inside `session_orchestrator.py`.
5. From that point onward, all output is captured, but the initial planning output is already lost.

### Discrepancies
- Turn headers and metadata are printed before Tee installation, so they bypass capture. Expected: all output during planning should be captured. (Resolved: confirmed via code reading.)

### Investigation History
1. User reports turn headers/metadata still missing after bug 22 fix. Hypothesis: these are printed via a different path.
2. grep found both are printed via `self._user_interactor.display_message()` in `planning_service.py` (lines 40, 154, 204, 209, 219).
3. Traced call sequence: `_handle_planning_and_execution()` -> `trigger_new_plan()` -> `generate_plan()` BEFORE `orchestrator.execute()` (which installs Tee). Confirmed root cause: timing mismatch.
4. Systemic audit confirmed no other pre-Tee `display_message` or `typer.echo` calls exist in `session_planner.py` or `session_lifecycle_manager.py`.

## Solution
(To be filled after implementation)
- **Root Cause:** The planning phase prints headers and metadata before the Tee is installed.
- **Fix:** Move Tee installation from `SessionOrchestrator.execute()` to `SessionLifecycleManager._handle_planning_and_execution()`, before the call to `trigger_new_plan()`. Guard `SessionOrchestrator.execute()` to skip installation if Tee is already active.
- **Preventative Measures:** Centralize Tee installation to a single point in the session lifecycle, ensuring all output is captured regardless of execution phase. Add regression tests that verify the entire session output is captured in history.log.
