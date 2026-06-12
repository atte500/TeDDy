# Slice: Console and Message Visibility
- **Status:** Planned
- **Type:** Feature
- **Milestone:** [N/A — Ad-hoc](/docs/project/slices/00-00-console-and-message-visibility.md)
- **Specs:** [Console & Message Visibility Task](/docs/project/tasks/console-and-message-visibility.md)
- **Prototype:** [spikes/prototypes/console_and_message_visibility/](/spikes/prototypes/console_and_message_visibility/)
- **Component Docs:** [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md)
- **Scope Slug:** `00-00-console-and-message-visibility`

## Business Goal
Improve user visibility into session execution by logging the plan status emoji/title and user messages to the terminal console.

## Scenarios

### Scenario 1: Emoji + Title printed before action logs
> As a user running a session, I want to see the plan status emoji and title printed in the terminal before any action execution logs, so that I have semantic context.

```gherkin
Given a plan with title "Test Plan Title" and status "Draft"
When the session orchestrator executes the plan
Then the console prints "🟢 Test Plan Title" before any action logs
```

### Scenario 2: User message printed after action logs
> As a user, I want to see my additional message logged to the terminal after all actions have executed, in the format `User Message:` followed by content on a new line.

```gherkin
Given a plan with a user-provided message "Fix the index"
When all actions have been executed
Then the console prints "User Message:" followed by "Fix the index" on the next line
```

### Scenario 3: No user message yields no extra output
> As a user, when I do not provide an additional message, I want no "User Message:" line printed to the terminal.

```gherkin
Given a plan without a user-provided message
When all actions have been executed
Then no "User Message:" line is printed
```

### Scenario 4: Full terminal output format
> As a user, the full terminal output during session execution should follow the format: emoji+title, action logs, user message (if present).

```gherkin
Given a plan with title "Test Plan Title" and a user message "Fix the index"
When the session orchestrator executes the plan
Then the terminal output matches:
🟢 Test Plan Title
READ - Read the project readme.
SUCCESS

User Message:
Fix the index
```

## Edge Cases
- **Empty Plan Title**: If the plan has no H1 heading, the status line should print only the emoji (e.g., `🟢`).
- **Unknown Status**: If plan status is missing or unknown, default to green (🟢).
- **Empty User Message**: If user provides a blank message, no `User Message:` line should be printed.
- **Non-session mode**: The feature should not affect stateless (`--yolo`) execution; only session mode.

## Implementation Plan
Two additions to `SessionOrchestrator.execute()`:

1. **Emoji + Title console line:** After the plan is resolved and validated, and before `self._execution_orchestrator.execute()` is called, print to stderr:
   - Status emoji (🟢🟡🔴) and plan title via `typer.secho(f"{emoji} {title}", fg=typer.colors.GREEN, err=True)`.
   - Helper function `_get_status_emoji(status)` maps status strings to emojis (Draft/To De-risk/Planned/Completed → 🟢, In Progress → 🟡, Blocked → 🔴, unknown → 🟢).

2. **User Message console line:** After `self._execution_orchestrator.execute()` returns the report, and before turn transition, check for a user-provided message:
   - Look in `plan.metadata.get("user_request")` (which has been proactively set from the `message` parameter or from the report's `user_request` metadata).
   - If non-empty, print `typer.secho("User Message:", fg=typer.colors.WHITE, err=True)` then `typer.secho(content, err=True)`.
   - The message must be captured before the original execute call and stored in `plan.metadata["user_request"]` to ensure it is available regardless of the report assembler's behavior.

**Key implementation notes from prototype:**
- Both lines must be printed to **stderr** (`err=True`) to match the existing action log output format.
- The emoji+title line must appear **before** any action logs.
- The user message line must appear **after** all action logs.
- The message is provided via the CLI `-m` flag or the TUI `m` key.
- In non-session mode (`--yolo`), only the emoji+title line should be printed; user message printing depends on whether a message was passed.

3. Update unit tests in `test_session_orchestrator.py` to verify:
   - Emoji+title line is printed with correct emoji and appears before action logs.
   - User message line is printed with correct format and appears after action logs.
   - No extraneous output when no user message is provided.

## Deliverables
- [ ] **Logic** - Add `print_plan_status()` helper in SessionOrchestrator
- [ ] **Logic** - Add `log_user_message()` helper in SessionOrchestrator
- [ ] **Wiring** - Integrate both calls into `SessionOrchestrator.execute()`
- [ ] **Test** - Unit tests for console visibility and message logging

## Implementation Notes
- Prototyped in `spikes/prototypes/console_and_message_visibility/` using a shadow file that wraps `SessionOrchestrator.execute()` with the visibility features.
- The prototype revealed that `CliRunner(mix_stderr=True)` interleaves stdout and stderr non-chronologically. Use `mix_stderr=False` and assert on `result.stderr` for terminal visibility assertions.
- The user message must be proactively stored in `plan.metadata["user_request"]` before calling `original_execute` because the execution report assembler may not propagate the `message` parameter to report metadata for all code paths.
- The output format confirmed: emoji+title line before action logs, `User Message:` label on its own line, content on next line.

## Verification
1. `poetry run pytest tests/suites/unit/core/services/test_session_orchestrator.py -v`
2. `poetry run pytest tests/suites/integration/core/services/test_session_orchestration_integration.py -v`
3. `poetry run python spikes/prototypes/console_and_message_visibility/probe_visibility.py --scenario 1`
   - Expect: stderr = `🟢 Test Plan Title\n`, stdout contains execution report with SUCCESS
4. `poetry run python spikes/prototypes/console_and_message_visibility/probe_visibility.py --scenario 2`
   - Expect: stderr = `🟢 Test Plan Title\nUser Message:\nFix the index\n`, stdout contains execution report with SUCCESS
