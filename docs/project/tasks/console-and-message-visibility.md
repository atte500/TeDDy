# Task: Console and Message Visibility

## Business Goal
Improve user visibility into session execution by logging the plan status emoji/title and user messages to the terminal console.

## Context
Currently, session mode execution provides limited console feedback. Two features are needed:
1. **Console Visibility:** After the metadata block and before action logs, log the plan status emoji and title (e.g., `🟢 Implement safety limits`) to provide semantic context in terminal scrollback.
2. **Message Visibility:** When a user provides an additional message during review (via TUI 'm' key or message replies), log it to the console after all actions have executed in the format `User Message: [content]`.

Both features require changes to the `ExecutionOrchestrator.execute` flow (the `SessionOrchestrator` delegates to `ExecutionOrchestrator` for the actual action execution).

## Implementation Steps

### Step 1: Add emoji extraction helper
- **File:** [src/teddy_executor/core/services/execution_orchestrator.py](/src/teddy_executor/core/services/execution_orchestrator.py)
- **Change:** Add a private helper `_extract_status_emoji()` that extracts the status emoji (🟢, 🟡, 🔴) from `plan.metadata.get("Status", "")` using regex. This helper avoids importing from the textual reviewer adapter into the core service.

### Step 2: Inject Console Visibility line
- **File:** [src/teddy_executor/core/services/execution_orchestrator.py](/src/teddy_executor/core/services/execution_orchestrator.py)
- **Change:** After `_perform_interactive_review()` returns and before `_process_plan_actions()` is called, inject: `typer.secho(f"{emoji} {plan.title}", fg=typer.colors.CYAN, err=True)`

### Step 3: Inject Message Visibility line
- **File:** [src/teddy_executor/core/services/execution_orchestrator.py](/src/teddy_executor/core/services/execution_orchestrator.py)
- **Change:** After `_process_plan_actions()` returns and before `_report_assembler.assemble()` is called, inject:
  ```python
  resolved_message = message or plan.metadata.get("user_request")
  if resolved_message:
      typer.secho(f"User Message: {resolved_message}", fg=typer.colors.YELLOW, err=True)
  ```

### Step 4: Update tests
- **File:** [tests/suites/unit/core/services/test_execution_orchestrator.py](/tests/suites/unit/core/services/test_execution_orchestrator.py)
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
