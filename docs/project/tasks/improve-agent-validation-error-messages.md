# Task: Improve Agent Validation Error Messages

## Business Goal
Improve CLI error messages when users provide invalid agent names, making it clear what valid agents are available.

## Context
When a user runs `teddy start -a <invalid_name>`, they receive a generic error: `Configuration Error: Agent prompt '<name>' not found` followed by `Please update your configuration at: ...`. The message does not list valid agent names, forcing the user to guess or manually inspect `.teddy/prompts/`.

There are three error sites to fix:
1. CLI preflight check in `session_cli_handlers.py` (ConfigurationError path).
2. Session creation in `session_service.py` (ValueError path).
3. `get-prompt` command in `__main__.py`.

Additionally, similar "not found" errors for plan files and sessions could benefit from similar UX improvements (stretch goals).

## Implementation Steps

### Step 1: Add `get_available_agents()` to IPromptManager port
- **File:** [src/teddy_executor/core/ports/outbound/prompt_manager.py](/src/teddy_executor/core/ports/outbound/prompt_manager.py)
- **Change:** Add an abstract method `get_available_agents() -> list[str]` to the `IPromptManager` interface.

### Step 2: Implement `get_available_agents()` in PromptManager
- **File:** [src/teddy_executor/core/services/prompt_manager.py](/src/teddy_executor/core/services/prompt_manager.py)
- **Change:** Implement the method to list all `.xml` files in the `.teddy/prompts/` directory (canonical source), strip the `.xml` extension, and return the list of agent names. Use `IFileSystemManager` to check directory existence and list files. If the directory does not exist or is empty, return an empty list.

### Step 3: Update preflight check in session_cli_handlers.py
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** In `_run_cli_preflight_check()`, when `agent` is given and `prompt_manager.get_prompt_content(agent)` returns None:
  - Call `prompt_manager.get_available_agents()` to retrieve the list of valid agents.
  - Append a detailed error message: `"Agent prompt '{agent}' not found. Available agents: {', '.join(available)}"`.
  - **Critical:** If the agent error is the ONLY error collected, raise a plain `ValueError` instead of `ConfigurationError`. This way the outer `handle_new_session()` catches it with the generic `except Exception` and prints `f"Error: {e}"` WITHOUT showing the misleading "Please update your configuration at:" hint (agents come from `.teddy/prompts/`, not `config.yaml`). If there are other config errors mixed in (e.g., invalid API key), keep raising `ConfigurationError` so the config hint remains valid for the non-agent errors.

### Step 4: Fix session_service.py error message
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** In `create_session()`, when the prompt file does not exist at `.teddy/prompts/{agent}.xml`:
  - **Keep raising `ValueError`** (do NOT switch to `ConfigurationError`). The generic `except Exception` handler in `handle_new_session()` prints the error cleanly without the config hint.
  - Enrich the error message with available agents. The service has access to `IFileSystemManager`; use it to list `.teddy/prompts/*.xml` stems and include them in the message: `f"Agent prompt '{options.agent_name}' not found in .teddy/prompts/. Available agents: {', '.join(available)}"`.

### Step 5: Update get-prompt command error in __main__.py
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** In the `get_prompt` command handler, when `find_prompt_content(prompt_name)` returns None, include the list of available prompts in the error message. Create a `list_prompt_names()` helper in `src/teddy_executor/prompts.py` that lists `.xml` files from `.teddy/prompts/` (if exists) and falls back to built-in resources. Update the error message to: `"Error: Prompt '{prompt_name}' not found. Available prompts: {', '.join(available)}"`.

### Step 6 (Stretch): Improve "Plan file not found" error
- **File:** [src/teddy_executor/adapters/inbound/cli_helpers.py](/src/teddy_executor/adapters/inbound/cli_helpers.py)
- **Change:** In the function that raises `"Error: Plan file not found at '{plan_file}'"`, consider adding context about expected file format or how to generate a plan.

### Step 7 (Stretch): Improve "Session not found" error
- **File:** [src/teddy_executor/core/services/session_repository.py](/src/teddy_executor/core/services/session_repository.py)
- **Change:** When a session is not found, list available sessions from the `.teddy/sessions/` directory.

## Verification
1. Run `poetry run teddy start -a nonexistent` and verify the error message lists available agents.
2. Run `poetry run teddy get-prompt nonexistent` and verify it lists available prompts.
3. (Stretch) Test plan file and session not found errors with improvements.
4. Ensure existing tests still pass by running `poetry run pytest`.
