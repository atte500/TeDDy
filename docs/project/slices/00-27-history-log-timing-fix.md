# Slice: History.log Timing Fix – Capture Planning Output
- **Status:** In Progress
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
- [x] **Contract** - Expose `tee_active` property on `SessionLifecycleManager` to allow `SessionOrchestrator` to query Tee installation state.
- [x] **Harness** - Create test fixtures for verifying Tee installation timing (writeable log path, Tee-active flag detection).
- [x] **Logic** - Move Tee installation from `SessionOrchestrator.execute()` to `SessionLifecycleManager._handle_planning_and_execution()` before `trigger_new_plan()`, with `try/finally` cleanup and a contract flag for guard.
- [x] **Logic** - Add a guard in `SessionOrchestrator.execute()` to check `SessionLifecycleManager.tee_active` before installing Tee and skip if already active.
- [x] **Wiring** - Add unit tests for the new timing and guard behavior in `test_session_lifecycle_manager.py` and `test_session_orchestrator.py`.
- [ ] **Wiring** - Add integration tests for session execution verifying history.log contains planning output (turn header, metadata lines).

## Implementation Notes

### Completed: Contract - tee_active property (2026-06-10)

- Added `self.tee_active = False` to `SessionLifecycleManager.__init__()` in `session_lifecycle_manager.py`.
- Created `TestTeeActiveContract` test class in `test_session_lifecycle_manager.py` with `test_tee_active_exists_and_defaults_to_false`.
- The attribute is a plain boolean flag, defaulting to `False`, fulfilling the contract requirement for `SessionOrchestrator` to query Tee installation state.
- No refactoring needed — the change is minimal and follows all DI purity rules (the `manager` test fixture uses proper Constructor Injection via `SessionPorts`).
- Full test suite: 877 passed, 3 skipped (no regressions).

### Completed: Harness - Test fixtures for Tee installation timing (2026-06-10)

- Added `is_tee_active()` helper function in `tests/harness/setup/composition.py` that checks if `sys.stderr` is a `_TeeWriter` instance.
- Added `tee_log_path` fixture that creates a temporary writeable `.log` file in the system temp directory and cleans it up after the test.
- Added `installed_tee` fixture that installs Tee on the log path and ensures proper cleanup via `__exit__` even if the test fails.
- Exported all three in `tests/conftest.py` for global availability.
- Full test suite: 877 passed, 3 skipped (no regressions).

### Completed: Logic - Move Tee installation to SessionLifecycleManager + Guard (2026-06-10)

- **`session_lifecycle_manager.py`:**
  - Added `tee_active = False` as class-level attribute (required for `POSIXPathMock` spec compatibility).
  - Fixed import ordering (E402): moved `IRunPlanUseCase` and `SessionState` imports above `TYPE_CHECKING` block.
  - Added `Tee as _Tee` import and a `logger` for cleanup failure logging.
  - In `_handle_planning_and_execution()`, Tee is installed before `trigger_new_plan()` using `Path(turn_dir).parent / "history.log"` as the log path (session root).
  - Defensive guard: if the resolved log path equals the project root, redirects to `.tmp/history.log`.
  - `try/finally` guarantees Tee cleanup and `tee_active = False` reset, even on cancellation or exception.
  - If planning is cancelled (`trigger_new_plan` returns `CANCELLED`), the `finally` block cleans up Tee.
- **`session_orchestrator.py`:**
  - Re-added `Tee as _Tee` import and `logger`.
  - Tee installation in `execute()` is now guarded by `not self._lifecycle_manager.tee_active`.
  - When the lifecycle manager has already installed Tee (during planning), the orchestrator skips installation entirely.
  - Proper `try/finally` cleanup is retained for the orchestrator's own Tee installation.
- **Regression fixes during implementation:**
  - Fixed log path derivation: `.parent` (not `.parent.parent`) is the session root.
  - Fixed indentation error when removing the orphaned `try` block from a previous edit.
- **[DEBT]** Pre-existing Ruff violations in `session_orchestrator.py`:
  - `PLR0915` (too many statements) in `execute()` – 56 statements exceed the 40 limit.
  - `PLR0912` (too many branches) in `execute()` – 16 branches exceed the 12 limit.
  - Both are structural issues in the orchestrator pattern. The function already suppresses `PLR0913` and `C901` via `# noqa`. These should be addressed in a future refactor.
- Full test suite: 877 passed, 3 skipped (no regressions).

### Completed: Wiring - Unit tests for timing and guard behavior (2026-06-10)

- **`TestTeeTiming`** class in `test_session_lifecycle_manager.py`:
  - `test_tee_installed_before_planning` – verifies that `tee.__enter__()` is called before `trigger_new_plan()`. Uses a call-order log with direct return values to avoid recursion.
  - `test_tee_active_set_during_planning` – verifies that `tee_active` is `True` during planning and reset to `False` after execution. Captures `tee_active` inside the `trigger_new_plan` side-effect.
  - `test_tee_cleaned_up_on_cancellation` – verifies that `tee.__exit__()` is called and `tee_active` is reset when planning returns `CANCELLED`.
- **`TestTeeGuard`** class in `test_session_orchestrator.py`:
  - `test_orchestrator_skips_tee_when_lifecycle_active` – sets `lifecycle_manager.tee_active = True` and confirms `_Tee` is never instantiated.
  - `test_orchestrator_installs_tee_when_not_active` – sets `lifecycle_manager.tee_active = False` with a session plan path, and confirms `_Tee` is instantiated and entered.
- **Regression fixes:**
  - Fixed cancellation return value in `_handle_planning_and_execution` (was returning `"CANCELLED"` instead of `turn_dir`).
  - Added `get_session_state` mock return value in the two timing tests that exercise the post-planning path.
- Full test suite: 882 passed, 3 skipped (no regressions).

- **`session_lifecycle_manager.py`:**
  - Added `tee_active = False` as class-level attribute (required for `POSIXPathMock` spec compatibility).
  - Fixed import ordering (E402): moved `IRunPlanUseCase` and `SessionState` imports above `TYPE_CHECKING` block.
  - Added `Tee as _Tee` import and a `logger` for cleanup failure logging.
  - In `_handle_planning_and_execution()`, Tee is installed before `trigger_new_plan()` using `Path(turn_dir).parent / "history.log"` as the log path (session root).
  - Defensive guard: if the resolved log path equals the project root, redirects to `.tmp/history.log`.
  - `try/finally` guarantees Tee cleanup and `tee_active = False` reset, even on cancellation or exception.
  - If planning is cancelled (`trigger_new_plan` returns `CANCELLED`), the `finally` block cleans up Tee.
- **`session_orchestrator.py`:**
  - Re-added `Tee as _Tee` import and `logger`.
  - Tee installation in `execute()` is now guarded by `not self._lifecycle_manager.tee_active`.
  - When the lifecycle manager has already installed Tee (during planning), the orchestrator skips installation entirely.
  - Proper `try/finally` cleanup is retained for the orchestrator's own Tee installation.
- **Regression fixes during implementation:**
  - Fixed log path derivation: `.parent` (not `.parent.parent`) is the session root.
  - Fixed indentation error when removing the orphaned `try` block from a previous edit.
- **[DEBT]** Pre-existing Ruff violations in `session_orchestrator.py`:
  - `PLR0915` (too many statements) in `execute()` – 56 statements exceed the 40 limit.
  - `PLR0912` (too many branches) in `execute()` – 16 branches exceed the 12 limit.
  - Both are structural issues in the orchestrator pattern. The function already suppresses `PLR0913` and `C901` via `# noqa`. These should be addressed in a future refactor.
- Full test suite: 877 passed, 3 skipped (no regressions).

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
