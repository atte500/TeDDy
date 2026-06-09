# Task: Session History Log (history.log) Implementation

## Business Goal
Provide a persistent, chronological log of all turn activity in a session for easy auditing, review, and debugging. Users can open `history.log` to see exactly what happened in each turn without navigating individual turn directories.

## Context

### The Feature
The Session History Log (`history.log`) is a plain-text chronological log of all turn activity in a session. It mirrors the console output that the user sees during execution, captured via a tee mechanism that writes the same lines to both stdout and the log file.

### Key Design Decisions
- **Console Fidelity:** The log records exactly what the user sees printed to the console during execution.
- **Mode Independence:** The exact same content is generated in both `-y` and interactive TUI modes (the TUI's alternate screen buffer does not interfere).
- **Minimal Changes:** A lightweight Tee wrapper duplicates stdout writes to the log file, avoiding duplication of console printing logic.
- **Append-Only:** The log is opened in append mode and flushed after each write to prevent data loss on crash.
- **All Turns Logged:** Both successful turns and validation failure turns are logged (validation failure turns show `FAILURE` status). The spec explicitly logs all turns for debugging.

### Reference Files
- [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md) — The full specification with exact format, generation mechanism, and edge cases.
- [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py) — The main orchestrator where the Tee should be installed (execute() method, lines ~18-170).
- [src/teddy_executor/core/services/session_lifecycle_manager.py](/src/teddy_executor/core/services/session_lifecycle_manager.py) — Manages turn lifecycle; `finalize_turn()` is called after execution to persist the report.
- [src/teddy_executor/core/services/action_executor.py](/src/teddy_executor/core/services/action_executor.py) — Where action logs are printed during `confirm_and_dispatch()` via `_action_dispatcher.dispatch_and_execute()`.
- [src/teddy_executor/adapters/inbound/cli_helpers.py](/src/teddy_executor/adapters/inbound/cli_helpers.py) — Contains `echo_and_copy()` which prints to stdout via `typer.echo()`.

## Implementation Steps

### Step 1: Create `Tee` Utility Class
- **File:** [src/teddy_executor/core/utils/io.py](/src/teddy_executor/core/utils/io.py) (new file)
- **Change:**
  Create a `Tee` context manager class that duplicates `sys.stdout` writes to a log file. The class:

  1. **Constructor:** Takes a `Path` to the log file.
  2. **`__enter__`:** Saves the original `sys.stdout`, opens the log file in append mode (`"a"`, UTF-8 encoding), and installs a custom writer object as `sys.stdout`.
  3. **Custom writer:** A simple class (or closure) with a `write(text)` method that:
     - Calls `original_stdout.write(text)` and `original_stdout.flush()` (to preserve console output).
     - Calls `log_file.write(text)` and `log_file.flush()` (to write to the log file).
     - Forwards `flush()` to both handles.
     - Forwards `isatty()` from the original stdout.
  4. **`__exit__`:** Restores the original `sys.stdout` and closes the log file handle.

  Edge cases:
  - **File open failure:** If the log file cannot be opened (e.g., permissions), log a debug warning and skip tee'ing entirely. The session continues without a history.log.
  - **Unicode characters:** The file is opened with `encoding="utf-8"`.
  - **Very long lines:** No trimming needed — forward verbatim.
  - **Flush on each write:** Ensures no data loss on crash.

### Step 2: Install Tee in `SessionOrchestrator.execute()`
- **File:** [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py)
- **Change:**
  Modify the `execute()` method to install the Tee at the very start, before any console output-producing code (plan parsing, context preparation, validation, execution). This ensures ALL stdout output for the turn is captured.

  1. After line `is_session = self._is_session_mode(plan_path)` (approx line 30), add:
     ```python
     tee = None
     if is_session and plan_path:
         try:
             from teddy_executor.core.utils.io import Tee
             history_log_path = str(Path(plan_path).parent.parent / "history.log")
             tee = Tee(Path(history_log_path))
             tee.__enter__()
         except Exception as e:
             logger.debug("Failed to initialize history.log Tee: %s", e)
     ```

  2. Wrap the core logic in a try/finally block:
     ```python
     try:
         # ... rest of execute() method unchanged ...
         return report
     finally:
         if tee:
             try:
                 tee.__exit__(None, None, None)
             except Exception as e:
                 logger.debug("Failed to close history.log: %s", e)
     ```

  3. Ensure the `import` statement for `Path` is present at the top of the file (it's already imported: `from pathlib import Path`).

  What the Tee captures (all stdout during execution):
  - Metadata header (turn number, plan title, agent, model, context, cost)
  - Action descriptions and statuses
  - Validation errors and messages
  - Turn transition messages
  - Any errors or warnings printed to stdout during the turn lifecycle

  **Important:** The `execute()` method may return early via the replanning paths (`_prepare_plan_parsing` returns an ExecutionReport on validation failure, `_handle_logical_validation_errors` returns an ExecutionReport). The try/finally ensures the Tee is properly cleaned up regardless of which path exits.

### Step 3: Ensure Metadata Header is Printed to stdout
- **File:** [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py) (or the service that currently prints it)
- **Change:**
  The spec requires the following metadata header in `history.log`:
  ```
  [NN] <plan-title> | Waiting for <agent-name> to respond...
  • Model: <model-string>
  • Context: <current-context> / <max-context> tokens
  • Session Cost: $<cost>
  ```

  **Search for existing header printing:**
  Use `git grep` to find where this header is currently printed to stdout. Likely locations:
  - `session_service.py` or `session_manager.py` — during turn initialization
  - `session_lifecycle_manager.py` — during resume/execute
  - The metadata might be constructed from `meta.yaml` values

  **If the header IS already printed to stdout:**
  The Tee already captures it. No change needed. Verify by running a session and checking stdout for the header pattern.

  **If the header is NOT printed to stdout** (e.g., it only exists in `meta.yaml` or is only shown in the TUI):
  Add explicit `typer.echo()` calls in `SessionOrchestrator.execute()` to print the header before the execution call. Construct the header from:
  - Turn number (`NN`): Extract from `plan_path` (the parent directory name is the turn number, e.g., `"01"`). Use `Path(plan_path).parent.name`.
  - Plan title: `plan.title` after parsing (available after `_prepare_plan_parsing`).
  - Agent name: `plan.metadata.get("Agent") or plan.metadata.get("agent", "Unknown")`.
  - Model string: `self._config_service.get_setting("llm.model", "unknown")`.
  - Context tokens: Check `project_context` (has `total_tokens`) or `self._llm_client.get_context_window()`.
  - Session cost: `self._session_service.get_cumulative_cost(session_name)` — but `session_name` needs to be extracted from `plan_path`. Extract via `Path(plan_path).parent.parent.name`.

  The `typer.echo()` calls should be placed before the execution call (after validation passes) so they appear in both successful and validation-failure turns.

  **Placement example** (after validation passes, before execution):
  ```python
  if is_session and plan_path:
      turn_num = Path(plan_path).parent.name
      agent = plan.metadata.get("Agent") or plan.metadata.get("agent", "Unknown")
      model = self._config_service.get_setting("llm.model", "unknown")
      typer.echo(f"[{turn_num}] {plan.title} | Waiting for {agent} to respond...")
      typer.echo(f"• Model: {model}")
      # ...context and cost...
  ```

### Step 4: Handle Edge Cases
- **File:** [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py)
- **Change:**

  **Validation Failures:**
  The Tee is installed at the START of `execute()`, so validation failure output is automatically captured. The spec says validation failures should be logged with `FAILURE` status — this is already satisfied since the validation error messages printed to stdout will be captured. The turn still gets a header block.

  **Replanning:**
  When `_prepare_plan_parsing` or `_handle_logical_validation_errors` trigger a replan, the current turn's output is captured by the Tee (installed before these calls). The replan creates a new plan in the NEXT turn directory but does NOT execute it — that happens in the next `resume()` call (next iteration of `_orchestrate_session_loop`), which will have its own `execute()` call with its own Tee. So each turn's output is isolated correctly.

  **Message Turns (Communication Turns):**
  Turns with only a `## Message` block produce `MESSAGE - <content>` lines to stdout (if they're printed). The Tee captures them. No special handling needed.

  **Non-Session Mode:**
  The Tee is only installed when `is_session` is True. Standalone `teddy execute` calls do not produce a history.log. Verify this by checking `is_session` before installing.

  **`--yolo` / `-y` Mode:**
  The Tee captures stdout regardless of TUI/interactive mode. The same `history.log` content is produced in both modes, as required by the spec.

  **Session Branching:**
  If a session is branched by copying the directory, `history.log` is copied with it. Each branch has its own log continuing from the branch point. This is acceptable per the spec.

  **Turn Number Formatting:**
  The spec uses zero-padded 2-digit turn numbers (`01`, `02`, ..., `99`). Ensure `Path(plan_path).parent.name` returns the correct format. If the turn directory uses 2-digit names (as per session convention), this is automatic.

### Step 5: Add Tests
- **File:** [tests/suites/unit/core/services/test_session_orchestrator.py](/tests/suites/unit/core/services/test_session_orchestrator.py) (existing file) or [tests/suites/unit/core/utils/test_io.py](/tests/suites/unit/core/utils/test_io.py) (new file for Tee tests)
- **Change:**

  **Tee unit tests** (new test file `tests/suites/unit/core/utils/test_io.py`):
  1. **Test basic tee:** Capture stdout writes and verify both original stdout and log file receive the content.
  2. **Test flush propagation:** Verify `flush()` is called on both handles.
  3. **Test `isatty()`:** Verify it returns the same as original stdout.
  4. **Test context manager restore:** After `__exit__`, verify `sys.stdout` is the original object.
  5. **Test exception safety:** If the file cannot be opened, verify no exception propagates and stdout is unmodified.

  **SessionOrchestrator integration tests** (in existing test file):
  6. **Test history.log creation:** When a session turn executes (mocked), verify a `history.log` file is created in the session root directory.
  7. **Test format correctness:** Verify the log file contains lines matching the spec format (turn header, metadata bullets, action lines with statuses).
  8. **Test validation failure logging:** Simulate a validation failure and verify the log captures the header and error output.
  9. **Test non-session mode:** When `is_session` is False, verify no `history.log` is created.
  10. **Test append mode:** Simulate two successive turns and verify the log file contains both turns' content (appended, not overwritten).
  11. **Test stdout restoration on exception:** Force an exception in `execute()` and verify `sys.stdout` is restored to its original value.
  12. **Test Tee failure isolation:** If the Tee fails to open the log file, verify the session continues normally without errors.

## Verification

1. **History log creation:** Start a session with `teddy start -m "test message" -a developer`. After the first turn completes, verify `.teddy/sessions/<session_name>/history.log` exists and is non-empty.
2. **Format check:** Open `history.log` and verify it matches the spec format:
   ```
   [01] Plan Title | Waiting for developer to respond...
   • Model: openrouter/...
   • Context: ... / ... tokens
   • Session Cost: $0.0000

   CREATE - description
   SUCCESS
   ```
3. **Multiple turns:** Run 3+ turns in the session. Verify each turn's content is chronologically appended to the same `history.log`.
4. **Validation failure:** Trigger a validation error (e.g., by having the agent generate an invalid plan). Verify the log still captures the header and validation error output before the failure.
5. **`-y` mode:** Resume the session with `teddy resume -y`. Verify the log content is identical in format to interactive mode.
6. **Non-session:** Run `teddy execute` (standalone) with a valid plan. Verify no `history.log` is created.
7. **Branching:** Manually copy a session directory. Verify the copy's `history.log` reflects the branch point correctly.
8. **Existing tests pass:** Run `poetry run pytest` to ensure no regressions.
9. **Stdout restoration:** Run the test suite and verify there are no side-effects on stdout from the Tee (no stray output, no leaked file handles).
