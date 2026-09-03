# Bug: Pipeline MESSAGE Response Logged as "User Message"

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [Pipeline Automation](/docs/project/slices/00-18-pipeline-automation.md)
- **Specs:** N/A

## Symptoms

### Expected Behavior
Running `teddy start -a assistant -p -m "Say hello and ask how I am"` should break cleanly after the first MESSAGE action. The terminal output should not print the agent's message under a "User Message:" header since there is no user message in pipeline mode.

### Actual Behavior
The agent's MESSAGE response (e.g., "Hello Raphael! Welcome to the TeDDy session...") is printed under "User Message:" in the terminal output, which is semantically incorrect — the content is the agent's message, not a user message.

### Steps to Reproduce
1. Run: `teddy start -a assistant -p -m "Say hello and ask how I am"`
2. Observe the terminal output contains:

```
🟢 Say Hello and Ask How the User Is

User Message:
Hello Raphael! Welcome to the TeDDy session. I'm ready and eager to assist.
```

3. The "User Message:" label is misleading because the content is the agent's response.

## Context & Scope

### Regressing Delta
The pipeline MESSAGE break fix (commit 1b696aac) introduced a synthetic ActionLog in `ActionExecutor.confirm_and_dispatch()` when `pipeline=True`. This ActionLog's `details` field contains the agent's message content (from `action.params["content"]`). The `_print_user_message` function in `session_orchestrator.py` has a fallback (priority 3) that extracts MESSAGE action replies from `action_logs` and prints them under "User Message:". In pipeline mode, this fallback incorrectly captures the agent's message as a "user message".

### Environmental Triggers
- Requires pipeline mode (`-p`).
- Agent must produce a MESSAGE action (which the assistant does by default).
- The MESSAGE action log must have non-empty `details` (which the pipeline fix ensures).

### Ruled Out
- The pipeline break fix is correct and works as intended.
- The `_print_user_message` function works correctly in interactive and YOLO modes.
- The MESSAGE action log fallback (priority 3) was introduced for Bug 16/17 and is needed in non-pipeline modes for user reply display.

## Diagnostic Analysis

### Causal Model
In pipeline mode, the synthetic ActionLog created by `ActionExecutor.confirm_and_dispatch()` has `details` set to the agent's message content (from `action.params["content"]`). In `SessionOrchestrator.execute()`, `_print_user_message` is called with:
- `user_reply = plan.metadata.get("user_request", "")` — empty, because no real user replied
- `action_logs = report.action_logs` — contains the synthetic MESSAGE ActionLog

The `_print_user_message` priority 3 fallback iterates `action_logs`, finds the MESSAGE entry with non-empty `details`, and prints its content under "User Message:". This is incorrect in pipeline mode because the content is the agent's message, not a user reply.

### Discrepancies
- None yet (investigation just started).

### Investigation History
1. **Hypothesis:** The `_print_user_message` priority 3 fallback captures the synthetic MESSAGE ActionLog's details in pipeline mode. **Observation:** Confirmed by reading the code. **Conclusion:** The fix is to skip the MESSAGE action log fallback in `_print_user_message` when `pipeline=True`.

## Solution

### Root Cause
The `_print_user_message` function in `session_orchestrator.py` has a Priority 3 fallback that extracts MESSAGE action replies from `report.action_logs` and prints them under "User Message:". The pipeline MESSAGE break fix (commit 1b696aac) introduced a synthetic ActionLog with `details` set to the agent's message content. In pipeline mode, this ActionLog is captured by Priority 3 and printed under the incorrect "User Message:" header.

### Fix
Modified the `_print_user_message` call site in `SessionOrchestrator.execute()` to detect `pipeline=True`. When in pipeline mode, the code iterates `report.action_logs` for a MESSAGE entry and prints its content under `--- MESSAGE from TeDDy ---` in cyan (`typer.secho(..., fg=typer.colors.CYAN)`), bypassing the `_print_user_message` function entirely. Non-pipeline modes (interactive, YOLO) are unaffected as they fall through to the existing `_print_user_message` call.

### Preventative Measures
The pipeline-specific output format is now explicit and isolated, matching the normal ask loop styling. No other code path needed modification.