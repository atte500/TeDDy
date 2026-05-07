# Bug: Windows Worker Crash in Session Resume Loop

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
In Windows CI, `test_start_enters_continuous_loop` causes a `pytest-xdist` worker crash: `node down: Not properly terminated`.
- **Expected:** The test completes the simulated session loop.
- **Actual:** Hard crash of the worker process.

## Context & Scope
### Regressing Delta
Commit `555d870c16f489a7c8b3a9001eb4566bee722387`: "refactor(core): extract SessionPruningService and resolve quality gates". This commit altered the core loop in `SessionOrchestrator` and added automated pruning logic.

### Environmental Triggers
- Windows OS (win32).
- `pytest-xdist` parallel execution.
- Continuous loop execution in `SessionOrchestrator.start()`.

### Ruled Out
- Ubuntu/macOS (passing).

## Diagnostic Analysis
### Causal Model
1. `test_start_enters_continuous_loop` triggers a multi-turn session.
2. Between turns, `SessionOrchestrator` calls `SessionPruningService.prune()`.
3. `SessionPruningService` attempted to read `plan.md` and `report.md` from numeric turn directories (e.g., `01/`, `02/`).
4. **Bug 1 (Logic):** The regex `turn-(\d+)` failed to match numeric directories, causing the pruning logic for failure history to be skipped.
5. **Bug 2 (Windows Race):** On Windows, the rapid read-after-write transition between turns caused `PermissionError` when the `SessionPruningService` tried to read files still being locked/buffered by the OS. This unhandled exception caused the worker crash.

### Discrepancies
- **Crash site changed.** Previous crash was in `test_tui_modifying_edit_action_content_succeeds`. Now it is in `test_start_enters_continuous_loop`. (Resolved: Both are caused by race conditions during rapid state transitions on Windows.)

### Investigation History
1. CI Log Analysis. Confirmed crash site in `test_start_enters_continuous_loop` on Windows.
2. Code Audit (Core). Checked `SessionOrchestrator` and `SessionLifecycleManager`. No explicit `while` loop found in core services for the session driver.
3. Code Audit (Pruning). Identified that `SessionPruningService` used an incorrect regex for turn directories.
4. Repair. Fixed regex to `(\d+)` and added defensive `OSError` handling for file reads.
5. Verification. Remote probe `debug/probe-10` passed on `windows-latest`.

## Solution
### Implemented Fixes
- Fixed `SessionPruningService` turn directory regex and added `OSError` handling to prevent crashes on locked files.

### Prevention
- The acceptance test `test_start_enters_continuous_loop` now serves as the regression test for this multi-turn synchronization logic on all platforms.
