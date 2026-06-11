# Task: Console and Message Visibility

## Business Goal
Improve user visibility into session execution by logging the plan status emoji/title and user messages to the terminal console.

## Context
Currently, session mode execution provides limited console feedback. Two features are needed:
1. **Console Visibility:** After the metadata block and before action logs, log the plan status emoji and title (e.g., `🟢 Implement safety limits`) to provide semantic context in terminal scrollback.
2. **Message Visibility:** When a user provides an additional message during review (via TUI 'm' key or message replies), log it to the console after all actions have executed in the format `User Message: [content]`.

Both features require changes to the `SessionOrchestrator.execute` flow.

## Implementation Steps

### Step 1: Inject Console Visibility header
- **File:** [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py)
- **Change:** After the plan is resolved, validated, and the metadata block is printed, inject a single line: `{emoji} {title}` (e.g., `🟢 Implement safety limits`). The emoji comes from the plan status (Green=🟢, Yellow=🟡, Red=🔴). The title comes from the plan's H1 heading. This line must appear before any action execution logs but after the metadata block.

### Step 2: Log user messages after execution
- **File:** [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py)
- **Change:** During the execution phase, detect if an additional user message was provided (from TUI 'm' key or message reply during review). After all actions have executed, log: `User Message: [content]`. This ensures the message is visible in the terminal scrollback for audit purposes.

### Step 3: Update tests
- **File:** [tests/suites/unit/core/services/test_session_orchestrator.py](/tests/suites/unit/core/services/test_session_orchestrator.py)
- **Change:** Add unit tests verifying:
  - Console Visibility line is printed with correct emoji mapping and title
  - Console Visibility line appears after metadata but before action logs
  - User messages are logged in `User Message: [content]` format
  - No user message results in no extraneous output

## Verification
1. Run unit tests: `poetry run pytest tests/suites/unit/core/services/test_session_orchestrator.py -v`
2. Run integration tests: `poetry run pytest tests/suites/integration/core/services/test_session_orchestration_integration.py -v`
3. Manual: Start a session and verify `🟢 {title}` appears after metadata
4. Manual: Provide a message during review and verify `User Message: [content]` appears after execution
