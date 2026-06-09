# Slice: Session History Log (history.log)
- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md)
- **Prototype:** [docs/project/tasks/25-history-log-implementation.md](/docs/project/tasks/25-history-log-implementation.md)
- **Component Docs:** [docs/architecture/core/services/session_orchestrator.md](/docs/architecture/core/services/session_orchestrator.md), [docs/architecture/core/utils/io.md](/docs/architecture/core/utils/io.md) (new)

## Business Goal
Provide a persistent, chronological log of all turn activity in a session for easy auditing, review, and debugging. Users can open `history.log` to see exactly what happened in each turn without navigating individual turn directories.

## Scenarios

> As a user, I want a persistent chronological log of all turn activity in my session so that I can easily audit what happened without navigating individual turn directories.

```gherkin
Given a session with at least one completed turn
When the first turn executes
Then a file named history.log exists in the session root directory
And it contains the metadata header for the turn
And it contains action log entries with statuses
```

> As a user, I want the log to be appended across multiple turns so that the full session history is available in one file.

```gherkin
Given a session with two completed turns
When both turns have executed
Then the history.log contains both turns' content in chronological order
And the second turn's content is appended after the first
```

> As a user, I want the log to be generated only in session mode so that standalone execute calls do not create a history.log.

```gherkin
Given a standalone execute call (non-session)
When the plan executes
Then no history.log is created in the session directory
```

## Edge Cases
- **File open failure**: If the log file cannot be opened (permissions), the session continues without a history.log. A debug warning is logged.
- **Validation failure turn**: The log captures the header and validation error output before the failure.
- **Communication turn (MESSAGE)**: The log shows the header and metadata block only, followed by `MESSAGE - <content>` and `SUCCESS`.
- **Non-session mode**: Tee is not installed; no history.log is created.
- **Session branching**: If a session directory is copied, the history.log is copied with it. Each branch has its own log continuing from the branch point.
- **Unicode characters**: File opened with UTF-8 encoding.
- **Flush on each write**: Ensures no data loss on crash.
- **Stdout restoration**: After Tee exits, sys.stdout is restored to original. Exception safety ensures this always happens.

## Deliverables
- [x] **Contract** - Define Tee class interface (takes Path, context manager, proxies write/flush/isatty to both stdout and log file).
- [x] **Logic** - Implement Tee class in `src/teddy_executor/core/utils/io.py`.
- [x] **Logic** - Add metadata header printing to stdout in SessionOrchestrator (required format: `[NN] <plan-title> | Waiting for <agent-name> to respond...`, plus model/context/cost bullets).
- [x] **Wiring** - Install Tee at start of SessionOrchestrator.execute() when is_session is True, with try/finally for cleanup.
- [x] **Harness** - Create test fixtures and helpers for Tee and history.log tests.
- [x] **Wiring** - Add unit tests for Tee class (basic tee, flush propagation, isatty, context manager, exception safety).
- [ ] **Wiring** - Add integration tests for history.log creation in SessionOrchestrator (format correctness, validation failure logging, non-session mode, append mode, stdout restoration, Tee failure isolation).
- [ ] **Cleanup** - Refactor `SessionOrchestrator.execute()` to reduce statement count (<40) and branch count (<12) to satisfy PLR0915/PLR0912 linting rules.

## Implementation Notes

### Contract - Tee class interface (DONE)
- Created `src/teddy_executor/core/utils/io.py` with `Tee` class and `_TeeWriter` proxy.
- `Tee.__enter__` opens log file in append mode, saves original stdout, installs `_TeeWriter` as `sys.stdout`.
- `Tee.__exit__` restores original stdout and closes log file.
- Graceful file-open failure: logs debug warning and returns without modifying stdout.
- `_TeeWriter.write()` flushes both handles after each write for crash safety.
- Tests: 3 unit tests covering constructor, context manager protocol, and real write propagation via `tmp_path`.
- Not tested yet: explicit flush propagation, isatty forwarding. Marked as debt.

### Logic - Metadata header printing (DONE)
- Added header printing in `SessionOrchestrator.execute()` after validation (step 3.5) and before execution (step 4), gated by `is_session and plan_path`.
- Format: `[NN] <title> | Waiting for <agent> to respond...` plus Model, Context, Session Cost bullets.
- Turn number extracted from `Path(plan_path).parent.name`.
- Agent name retrieved from `plan.metadata["Agent"]`.
- Model retrieved from `config_service.get_setting("llm.model", "unknown")`.
- Context tokens from `project_context.total_tokens` and `llm_client.get_context_window()`.
- Session cost from `session_service.get_cumulative_cost(session_name)`.
- **Regression fix**: Used `getattr(plan, "title", "Untitled")` instead of `plan.title` to avoid `AttributeError` on mock Plan objects that lack the attribute (7 tests were failing).
- **Import fix**: Moved `import typer` from local (inside methods) to module level to prevent `UnboundLocalError`.
- Test: `test_session_orchestrator_prints_metadata_header_when_session` verifies all four lines in stdout using `capsys`.

### Harness - Shared test fixtures and helpers (DONE)
- Extracted `_build_mocked_orchestrator` from `test_wiring_history_log.py` into a public function `build_mocked_orchestrator` in `tests/harness/setup/orchestrator_helpers.py`.
- Added `create_session_directory` helper that creates a standard session directory structure (turn dir + plan.md + meta.yaml) for reuse across multiple test files.
- Both functions are exported from `tests.harness.setup.orchestrator_helpers` and follow the existing harness pattern (Setup/Arrange helpers in `tests/harness/setup/`).
- `test_wiring_history_log.py` updated to import these helpers instead of defining its own private copies.

### Wiring - Tee installation in SessionOrchestrator.execute() (DONE)
- Tee installed after `is_session` detection (step 0) and before `# 1. Resolve Plan`.
- Installation follows this pattern:
  ```python
  if is_session and plan_path:
      session_dir = Path(plan_path).parent.parent
      history_log_path = session_dir / "history.log"
      tee = Tee(history_log_path)
      tee.__enter__()
  else:
      tee = None

  try:
      # ... original execute() body (steps 1-4b) indented by 4 spaces ...
  finally:
      if tee is not None:
          tee.__exit__(None, None, None)
  ```
- The try/finally ensures `sys.stdout` is always restored, even on exceptions.
- The Tee only captures stdout in session mode; standalone execute calls skip Tee installation.
- Implementation challenges: Multiple script attempts failed due to indentation mismatches. Final solution used a single Python script that replaced the entire block from `is_session = ...` through `return report` in one shot, avoiding double-indentation bugs.
- Test: `test_history_log_created_in_session_mode` verifies `history.log` exists with header content, and non-session mode does not create `history.log`.
- Test uses real `tmp_path` directory structure simulating a session turn.

### Wiring - Tee unit tests (DONE)
- Added 4 new tests to `tests/suites/unit/core/utils/test_io.py`:
  1. `test_tee_writer_flush_propagates_to_both_outputs` — verifies `_TeeWriter.flush()` does not close or break either stream.
  2. `test_tee_writer_isatty_returns_original_stdout_value` — verifies `isatty()` delegates to original stdout (StringIO returns False).
  3. `test_tee_restores_stdout_on_exception` — verifies `sys.stdout` is restored even when an exception is raised inside the context.
  4. `test_tee_handles_file_open_failure_gracefully` — verifies Tee skips when log file cannot be opened (e.g., permission error), stdout remains usable and restored on exit.
- All 7 tests (3 existing + 4 new) pass. Full suite: 867 passed, 3 skipped.
- The previously marked debt for explicit flush/isatty tests is now resolved by these tests.
- Tee installed after `is_session` detection (step 0) and before `# 1. Resolve Plan`.
- Installation follows this pattern:
  ```python
  if is_session and plan_path:
      session_dir = Path(plan_path).parent.parent
      history_log_path = session_dir / "history.log"
      tee = Tee(history_log_path)
      tee.__enter__()
  else:
      tee = None

  try:
      # ... original execute() body (steps 1-4b) indented by 4 spaces ...
  finally:
      if tee is not None:
          tee.__exit__(None, None, None)
  ```
- The try/finally ensures `sys.stdout` is always restored, even on exceptions.
- The Tee only captures stdout in session mode; standalone execute calls skip Tee installation.
- Implementation challenges: Multiple script attempts failed due to indentation mismatches. Final solution used a single Python script that replaced the entire block from `is_session = ...` through `return report` in one shot, avoiding double-indentation bugs.
- Test: `test_history_log_created_in_session_mode` verifies `history.log` exists with header content, and non-session mode does not create `history.log`.
- Test uses real `tmp_path` directory structure simulating a session turn.

## Implementation Plan
The implementation follows the task brief steps:
1. Create the Tee utility class in `src/teddy_executor/core/utils/io.py`.
2. Modify `session_orchestrator.py` to install the Tee at the start of `execute()` when in session mode, and ensure metadata header is printed to stdout.
3. Handle edge cases (validation failure, non-session, branching).
4. Add tests for Tee and SessionOrchestrator integration.

The Tee is a context manager that replaces `sys.stdout` with a custom writer that writes to both original stdout and the log file. It handles file open failures gracefully by logging a debug warning and skipping tee'ing.

Metadata header format:
```
[NN] <plan-title> | Waiting for <agent-name> to respond...
• Model: <model-string>
• Context: <current-context> / <max-context> tokens
• Session Cost: $<cost>
```

The turn number (NN) is extracted from the plan_path parent directory name. Plan title, agent name, model, context, and cost are available from the parsed plan, config, and session service after context preparation and before execution.

Key method: `SessionOrchestrator.execute()` installs Tee after determining `is_session` (after line ~30), wraps the rest of the method in try/finally to ensure Tee cleanup. The metadata header is printed after validation passes, before the actual execution call.

Test strategy:
- Tee unit tests: Verify write propagation, flush, isatty, context manager restore, exception safety.
- SessionOrchestrator tests: Use test doubles to simulate session turn execution and verify history.log creation and content.
- Integration: Run orchestration with mocked dependencies and assert file existence and format.
