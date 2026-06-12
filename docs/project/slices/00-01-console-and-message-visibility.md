# Slice: Console and Message Visibility
- **Status:** Planned
- **Type:** Feature
- **Milestone:** N/A (Ad-hoc)
- **Specs:** [Console and Message Visibility Task](../../tasks/console-and-message-visibility.md)
- **Prototype:** [00-console-visibility.py](../../../spikes/prototypes/00-console-visibility.py)
- **Component Docs:** [ExecutionOrchestrator](../../architecture/core/services/execution_orchestrator.md)
- **Scope Slug:** `console-message-visibility`

## Business Goal
Improve user visibility into session execution by logging the plan status emoji and title to the console after the metadata block, and logging any user-provided message after all actions execute.

## Scenarios

> As a user running a session, I want to see the plan status emoji and title on the console so that I have immediate semantic context in terminal scrollback.

```gherkin
Given a plan with status "ON-TRACK 🟢" and title "Implement safety limits"
When the plan is executed in interactive session mode
Then the console output contains "🟢 Implement safety limits"
And this line appears after the metadata header ("▶ Reviewing Plan: ...")
And this line appears before any action execution logs
```

> As a user, I want to see my provided message logged after actions execute so that there is an audit trail of my input in the terminal scrollback.

```gherkin
Given a plan with status "ON-TRACK 🟢" and title "Implement safety limits"
And the user provides a message "Let me refine this"
When the plan is executed
Then the console output contains "User Message: Let me refine this"
And this line appears after all action execution logs
And this line appears before the report summary
```

> As a user, I want to verify that no extraneous "User Message:" line appears when no message was provided.

```gherkin
Given a plan with status "ON-TRACK 🟢" and title "Implement safety limits"
And no user message is provided
When the plan is executed
Then the console output does not contain "User Message:"
```

## Edge Cases
- **Empty message on communication turn**: If the user provides an empty message during a communication turn (MESSAGE action), the session should terminate without creating a report.md. No "User Message:" line should appear.
- **Aborted session with new message**: If the user aborts execution and provides a new message, the message visibility line should log the new message, not the pre-existing one.
- **Emoji from status**: The emoji is extracted from the last character(s) of plan.metadata["Status"] using the regex [🟢🟡🔴]. If no emoji is found, a fallback "❓" is used.
- **Message from metadata**: If the message parameter is None, the system checks plan.metadata.get("user_request") for a stored message from TUI 'm' key captures.

## Implementation Plan

### Delta Analysis
Two changes are required in `ExecutionOrchestrator.execute()`:

1. **Console Visibility**: After `_perform_interactive_review()` returns (line ~270 in current code), inject a call to print the status emoji and title:
   ```python
   status_str = plan.metadata.get("Status") or ""
   emoji = _extract_status_emoji(status_str)
   typer.secho(f"{emoji} {plan.title}", fg=typer.colors.CYAN, err=True)
   ```

2. **Message Visibility**: After `_process_plan_actions()` returns (line ~275-279), before the report assembly, inject:
   ```python
   resolved_message = message or plan.metadata.get("user_request")
   if resolved_message:
       typer.secho(f"User Message: {resolved_message}", fg=typer.colors.YELLOW, err=True)
   ```

### Technical Strategy
- **Emoji Extraction**: Create a helper function `_extract_status_emoji` that uses `re.findall(r"[🟢🟡🔴]", status_str)` to find the emoji. This avoids importing from the textual reviewer helper (which is an adapter) into the core service. (See debt: consider consolidating into a shared utility in `core/utils/`)
- **Output Style**: Console visibility line uses `typer.colors.CYAN` (consistent with metadata header). Message visibility line uses `typer.colors.YELLOW` (consistent with other user notifications).
- **Order**: Both lines are printed to `stderr` via `typer.secho(..., err=True)`, matching the existing pattern in `ConsolePlanReviewer` and `cli_formatter.py`.
- **No interface change**: The `IRunPlanUseCase` interface is unchanged – the visibility lines are purely cosmetic additions to the `execute` method body.

### Deliverables
- [x] **Logic** - Console visibility injection in ExecutionOrchestrator.execute()
- [x] **Logic** - Message visibility injection in ExecutionOrchestrator.execute()
- [x] **Logic** - Emoji extraction helper function
- [x] **Harness** - Scenario prototype (completed, links in metadata)
- [ ] **Harness** - Unit tests for console output ordering in test_execution_orchestrator.py

## Implementation Notes
- The prototype monkey-patched ExecutionOrchestrator.execute() to verify the injection points. The production implementation should integrate the changes directly into the execute method.
- The emoji extraction uses regex on the plain status string (e.g., "ON-TRACK 🟢" → "🟢"). The Task definition originally targeted SessionOrchestrator; the prototype proved ExecutionOrchestrator is the correct location.
- No modifications to SessionOrchestrator, cli_formatter, or ConsolePlanReviewer are needed.
- **Debt:** The `_extract_status_emoji` helper duplicates emoji extraction logic found in `textual_plan_reviewer_helpers.py`. Consider consolidating into a shared utility in `core/utils/emoji.py` to avoid future drift.

## Verification
1. Run unit tests: `poetry run pytest tests/suites/unit/core/services/test_execution_orchestrator.py -v`
2. Run integration tests: `poetry run pytest tests/suites/integration/core/services/test_execution_orchestrator.py -v`
3. Manual: Start a session and verify `🟢 {title}` appears after metadata
4. Manual: Provide a message during review and verify `User Message: [content]` appears after execution
5. Run the scenario prototype: `cd /Users/raphaelatteritano/Desktop/dev/TeDDy copy && poetry run python spikes/prototypes/00-console-visibility.py --scenario default`
6. Run the prototype message scenario: `cd /Users/raphaelatteritano/Desktop/dev/TeDDy copy && poetry run python spikes/prototypes/00-console-visibility.py --scenario message`
