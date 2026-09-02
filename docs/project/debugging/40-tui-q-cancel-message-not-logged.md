# Bug: Message provided after 'q' (cancel) is not logged as User Message in terminal

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- **Expected:** When pressing 'q' in the TUI plan reviewer to cancel/abort a plan, the user is prompted "Plan aborted. How do you want to proceed?" and their reply should be printed to terminal as a "User Message:" (same as when pressing 'm').
- **Actual:** The message entered after the abort prompt is NOT printed to terminal. It may appear in report.md (if the report is assembled correctly) but is missing from the terminal output during the session.
- **Minimal Reproduction Steps:**
  1. Run `teddy start` in a session.
  2. When the plan is presented in TUI, press 'q' to cancel.
  3. When prompted "Plan aborted. How do you want to proceed?", type a message and press Enter.
  4. Observe that the terminal output does NOT show "User Message: <your message>". The session ends without printing the cancel message.

## Context & Scope

### Regressing Delta
Not a regression from a specific commit; this is a design-level ordering bug in `session_orchestrator.py`. The `execute()` method calls `_print_user_message()` BEFORE `_handle_aborted_session()`. The abort prompt (which captures the user's cancellation message) occurs inside `_handle_aborted_session()`, so the message is never printed to terminal.

### Environmental Triggers
- Session mode (`teddy start` without `--no-tui`)
- User presses 'q' in TUI to cancel/abort the plan
- The abort prompt must receive a non-empty reply

### Ruled Out
- The `_print_user_message` function itself works correctly for 'm' key messages and MESSAGE action replies (verified by Bug 17 fix).
- `_handle_aborted_session` correctly captures the new message and stores it in `plan.metadata["user_request"]`.
- The TUI `action_cancel()` handler correctly triggers plan abort by returning None.
- The `execution_orchestrator._handle_aborted_execution()` correctly assembles the abort report with the message.

## Diagnostic Analysis

### Causal Model
**Data Flow for 'q' Cancel Message (current, broken):**
1. User presses 'q' in TUI → `action_cancel()` → returns None (cancelled plan).
2. `execution_orchestrator.execute()` sees `reviewed_plan is None` → calls `_handle_aborted_execution(plan, start_time, message)` → returns report with ABORTED status.
3. Back in `session_orchestrator.execute()`, control continues past `_execution_orchestrator.execute()`.
4. `session_orchestrator` calls `_print_user_message(user_reply, ...)` where `user_reply = plan.metadata.get("user_request", "")`. At this point, `plan.metadata["user_request"]` is empty (the 'm' key wasn't pressed) → nothing printed.
5. `session_orchestrator` calls `_handle_aborted_session(report, plan)`, which:
   - Detects ABORTED status.
   - Prompts user: "Plan aborted. How do you want to proceed?"
   - Stores the user's reply in `plan.metadata["user_request"]`.
   - Returns the updated report.
6. Terminal output is already printed from step 4. The cancel message is never printed.

**Root Cause:** `_print_user_message` is called at line ~(after execution report returned) but BEFORE `_handle_aborted_session` which captures the cancel message. The ordering should be reversed: capture the abort message first, then print it.

### Discrepancies
- `_print_user_message` is positioned before `_handle_aborted_session` in the `execute()` method. This ordering means abort-captured messages are never printed.
- The `message` parameter passed to `_print_user_message` (as `user_reply`) is `plan.metadata.get("user_request", "")` which is empty at that point for 'q' cancel flows.

### Investigation History
1. [Turn 1-2] Read all relevant source files: `textual_plan_reviewer_app.py`, `textual_plan_reviewer_logic.py`, `execution_orchestrator.py`, `session_orchestrator.py`. Understood the data flow for 'm' and 'q' keys.
2. [Turn 3] Read `session_orchestrator.py` lines 140-210, confirmed ordering hypothesis: `_print_user_message` is called before `_handle_aborted_session`.
3. [Current] Created Case File. Will build MRE to confirm.

## Solution

### Root Cause
In `session_orchestrator.execute()`, the `_print_user_message()` call (line ~346) executes **BEFORE** `_handle_aborted_session()` (line ~352). The abort prompt — which captures the user's cancellation message via `user_interactor.ask_question("Plan aborted. How do you want to proceed?")` — occurs inside `_handle_aborted_session()`. By the time the message is stored in `plan.metadata["user_request"]` and `report.metadata["user_request"]`, the terminal output has already been printed.

This is a **temporal coupling** defect: `_print_user_message` (the reader) runs before `_handle_aborted_session` (the writer) populates the data it reads.

### Fix
Swap the two code blocks so that `_handle_aborted_session` runs **first** (capturing the abort message into `plan.metadata` and `report.metadata`), and `_print_user_message` runs **after** (reading the now-populated metadata).

**Before (broken):**
```python
# Print user message BEFORE abort handling
if is_session:
    user_reply = plan.metadata.get("user_request", "") if plan else ""
    action_logs = report.action_logs if report else []
    _print_user_message(
        user_reply, is_session, plan=plan, action_logs=action_logs
    )

# 4. Turn Transition
if is_session and plan_path:
    report = self._handle_aborted_session(report, plan)
    if report is None:
        import typer
        typer.secho("\nSession terminated.", fg=typer.colors.RED, err=True)
        typer.secho(
            "To continue the session, use `teddy resume [session_path]`.",
            err=True,
        )
        return None
    self._lifecycle_manager.finalize_turn(plan_path, report, plan=plan)
```

**After (fixed):**
```python
# 4. Turn Transition — handle abort FIRST, then print user message
if is_session and plan_path:
    report = self._handle_aborted_session(report, plan)
    if report is None:
        import typer
        typer.secho("\nSession terminated.", fg=typer.colors.RED, err=True)
        typer.secho(
            "To continue the session, use `teddy resume [session_path]`.",
            err=True,
        )
        return None
    self._lifecycle_manager.finalize_turn(plan_path, report, plan=plan)

# Print user message AFTER abort handling (so abort message is captured first)
if is_session:
    user_reply = plan.metadata.get("user_request", "") if plan else ""
    action_logs = report.action_logs if report else []
    _print_user_message(
        user_reply, is_session, plan=plan, action_logs=action_logs
    )
```

### Preventative Measures
1. **Code review rule:** Any sequence of `_print_*` / `_handle_*` calls in `session_orchestrator.py` must be reviewed for temporal coupling. The reader must come after the writer.
2. **Regression test:** The test `test_q_abort_message_printed_to_terminal` in `test_session_orchestrator.py` confirms that when an ABORTED report is returned, `_print_user_message` is called with the abort-captured message.
3. **Architecture note:** Future operations that collect user input and print it to terminal should ensure the input collection happens before the terminal print in the same scope.
