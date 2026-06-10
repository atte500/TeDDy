# Slice: History.log Timing Fix – Capture Planning Output
- **Status:** Draft
- **Type:** Bugfix
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md)
- **Prototype:** N/A
- **Component Docs:** [docs/architecture/core/services/session_orchestrator.md](/docs/architecture/core/services/session_orchestrator.md), [docs/architecture/core/utils/io.md](/docs/architecture/core/utils/io.md)

## Business Goal
Ensure that all console output generated during the planning phase of a session turn (turn header, metadata) is captured in `history.log`, providing a complete chronological record of every turn's activity.

## Scenarios

> As a user, I want the turn header printed during planning to appear in history.log, so that I can see when each turn started and which agent was invoked.

```gherkin
Given a session that is about to execute a new turn
When the planning phase runs and prints the turn header
Then the turn header line (e.g., "[01] session-name | Waiting for agent...") appears in history.log
```

> As a user, I want the metadata lines (Model, Context, Session Cost) printed during planning to appear in history.log, so that I can review the LLM configuration used for each turn.

```gherkin
Given a session that is about to execute a new turn
When the planning phase runs and prints metadata
Then all metadata lines (Model, Context, Session Cost) appear in history.log
```

> As a user, I want the Tee to be installed only once per turn to avoid duplicate capture or double-logging.

```gherkin
Given a session where Tee has already been installed during planning
When the execution phase attempts to install Tee again
Then the second installation is skipped (no duplicate log entries)
```

## Edge Cases
- **Non-session mode (standalone execute):** Tee should not be installed at all; the planning phase doesn't run in this mode.
- **Validation failure turn:** The planning phase still runs and prints headers/metadata before the validation failure occurs; these should be captured.
- **Replan (trigger_replan):** Planning runs again for the same turn; Tee should already be installed from the first planning attempt.
- **Cancel during planning:** If the user cancels planning (`trigger_new_plan` returns `CANCELLED`), Tee should be cleaned up.

## Deliverables
- [ ] **Logic** - Move Tee installation from `SessionOrchestrator.execute()` to `SessionLifecycleManager._handle_planning_and_execution()` before `trigger_new_plan()`.
- [ ] **Logic** - Add a guard in `SessionOrchestrator.execute()` to check if Tee is already installed (via a shared context or flag) and skip installation.
- [ ] **Harness** - Create test fixtures for verifying Tee installation timing (e.g., a flag to detect whether Tee was installed by the lifecycle manager).
- [ ] **Logic** - Ensure Tee is properly cleaned up if planning is cancelled or fails before execution.
- [ ] **Wiring** - Add unit tests for the new timing behavior in `test_session_lifecycle_manager.py`.
- [ ] **Wiring** - Add integration tests for session execution verifying history.log contains planning output.

## Implementation Notes
(To be filled during implementation)

## Implementation Plan
The fix involves two primary changes:

1. **`session_lifecycle_manager.py` – `_handle_planning_and_execution()`:**
   - Derive the `history.log` path from `turn_dir` (always `Path(turn_dir).parent.parent / "history.log"`).
   - Install the Tee **before** calling `self._session_planner.trigger_new_plan(turn_dir)`.
   - Wrap the entire method in `try/finally` to ensure Tee cleanup.
   - Set a flag (e.g., on the session ports or a class attribute) to signal that Tee is already installed.

2. **`session_orchestrator.py` – `execute()`:**
   - Check the Tee-installed flag before installing. If already installed, skip the Tee setup.
   - The flag could be as simple as checking if `sys.stderr` is already an instance of `_TeeWriter` or a boolean stored in a known location.

Alternative approach: Refactor Tee installation into a dedicated helper that can be called from both places, avoiding duplication.
