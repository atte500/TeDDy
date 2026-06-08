# Task: Correct Double Newlines Injection Point

## Business Goal
Apply `double_newlines()` transformation only to AI agent `## Message` content, not to all terminal output.

## Context
The current implementation calls `double_newlines()` inside `ConsoleInteractorAdapter.display_message()`, which affects ALL output (status messages, errors, telemetry). However, agent `## Message` content is displayed via `IUserInteractor.ask_question()` → `typer.echo()`, not through `display_message()`.

The fix must:
1. Remove the transformation from `display_message()`.
2. Apply it inside `ActionFactory._handle_message_protocol()` before calling `ask_question()`.

## Implementation Steps

### Step 1: Remove double_newlines from display_message
- **File:** `src/teddy_executor/adapters/outbound/console_interactor.py`
- **Change:** Remove the `from teddy_executor.core.utils.string import double_newlines` import and the `double_newlines(message)` call inside `display_message()`. The method becomes a transparent pass-through: `self._console.print(message)`.

### Step 2: Add double_newlines to message protocol handler
- **File:** `src/teddy_executor/core/services/action_factory.py`
- **Change:** In `_handle_message_protocol()`, import `double_newlines` and apply it to the `prompt` argument before passing to `method()`. Example:
```python
from teddy_executor.core.utils.string import double_newlines
prompt = double_newlines(kwargs.get("prompt", kwargs.get("content")))
```

### Step 3: Update display_message test
- **File:** `tests/suites/unit/adapters/outbound/test_console_interactor.py`
- **Change:** Update `test_display_message_doubles_newlines` to verify that `display_message` does NOT transform newlines (i.e., `"line1\nline2"` is printed as-is).

### Step 4: Add message protocol transformation test
- **File:** `tests/suites/unit/core/services/test_action_factory_message.py`
- **Change:** Add a test case verifying that `_handle_message_protocol` applies `double_newlines` to the message content before calling `ask_question`.

## Verification
1. Run `poetry run pytest` – all tests pass.
2. Confirm no regressions in `planning_service`, `session_orchestrator`, or `session_lifecycle_manager` tests.
3. Manually verify agent `## Message` content shows doubled newlines while status messages remain unchanged.
