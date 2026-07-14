# Bug: Message Action Responses Not Logged to Terminal

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

After the Bug 16 fix (which prevented MESSAGE action replies from leaking into the User Request section of report.md), responses to MESSAGE actions are no longer logged to the terminal during session mode.

**Expected behavior:** When a user types a reply to a MESSAGE action (LLM asks a question, user responds), the user's reply should appear in the terminal output (as it did before Bug 16).

**Actual behavior:** The user's reply no longer appears in the terminal output. It does appear correctly in the Action Log section of report.md (as "User Reply" in the MESSAGE action's details).

## Context & Scope

### Regressing Delta
The Bug 16 fix modified `_handle_action_in_loop` in `execution_orchestrator.py` to add a guard:
```python
if captured_message and action.type.upper() != "MESSAGE":
    plan.metadata["user_request"] = captured_message
```
This correctly prevents MESSAGE action replies from being stored in `plan.metadata["user_request"]`, but it also inadvertently removes the terminal output path for those replies.

The terminal output for user messages is handled by `_print_user_message` in `session_orchestrator.py`, which reads from `plan.metadata["user_request"]`. Since MESSAGE replies are no longer stored there, they are never printed to terminal.

### Environmental Triggers
- Session mode (`teddy start` without `--no-tui`)
- LLM generates a MESSAGE action (e.g., "What do you think about X?")
- User types a reply during execution

### Ruled Out
- The Jinja2 template and report renderer correctly display MESSAGE action replies in the Action Log section. The issue is NOT with the report.
- The `action_log.details` correctly captures the user's typed reply. The data is not lost.
- The Bug 16 fix itself is correct: MESSAGE replies should NOT appear in the User Request section.
- The `_print_user_message` function is the correct terminal output path and works for non-MESSAGE actions.

## Diagnostic Analysis

### Causal Model
**Data Flow for Terminal Output of MESSAGE Replies (after Bug 16):**
1. LLM generates a MESSAGE action during planning.
2. During execution, `confirm_and_dispatch` returns `(action_log, action_log.details)` — the user's typed reply.
3. In `_handle_action_in_loop`, the Bug 16 guard skips storing this in `plan.metadata["user_request"]`.
4. After execution, `session_orchestrator.execute()` calls `_print_user_message(user_reply, is_session, plan=plan)`.
5. `_print_user_message` reads `plan.metadata.get("user_request")` — which is empty for MESSAGE actions.
6. Result: The user's reply is never printed to terminal, though it IS correctly stored in `action_log.details`.

**Root Cause:** The terminal output path (`_print_user_message`) and the report User Request path (`plan.metadata["user_request"]`) are coupled through the same data source. The Bug 16 fix correctly severed the coupling for the report, but didn't establish an alternative terminal output path for MESSAGE action replies.

### Discrepancies
- After Bug 16, MESSAGE action replies are correctly in `action_log.details` but not in `plan.metadata["user_request"]`. This is correct for the report but breaks terminal logging.
- `_print_user_message` only reads from `plan.metadata["user_request"]`, which is no longer populated for MESSAGE actions.

### Investigation History
1. [Initial] Read case file 16 and related tests — understood Bug 16 fix.
2. [Data Flow Analysis] Traced MESSAGE action execution through `action_dispatcher.py`, `action_executor.py`, `execution_orchestrator.py`, and `session_orchestrator.py`.
3. [Terminal Output Path] Identified `_print_user_message` in `session_orchestrator.py` as the terminal logging function.
4. [Root Cause] `_print_user_message` relies on `plan.metadata["user_request"]` which Bug 16 no longer populates for MESSAGE actions.

## Solution

### Root Cause
After Bug 16's fix, `_handle_action_in_loop` in `execution_orchestrator.py` no longer stores MESSAGE action replies in `plan.metadata["user_request"]` (correctly, for the report). However, `_print_user_message` in `session_orchestrator.py` was the only terminal output path, and it only read from `plan.metadata["user_request"]`. Since MESSAGE replies were no longer stored there, they were never printed to terminal.

The terminal output path and the report User Request path were coupled through the same data source (`plan.metadata["user_request"]`). Bug 16 correctly severed the coupling for the report, but didn't establish an alternative terminal output path for MESSAGE action replies.

### Fix
Two changes in `session_orchestrator.py`:

1. **`_print_user_message` now accepts `action_logs` parameter:** When `plan.metadata["user_request"]` is empty (or when no direct `message` is provided), the function falls back to scanning `action_logs` for MESSAGE action replies and uses the last one found.
[Content truncated: Showing first 1000 of 1036 lines. Use the 'Lines' parameter to read specific line ranges (e.g., '2-25').]
