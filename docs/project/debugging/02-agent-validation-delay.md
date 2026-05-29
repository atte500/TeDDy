# Bug: Delayed Agent Validation in `start` Command

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When running `teddy start -a <invalid_agent>`, the CLI proceeds to ask the user "What are we working on?" before failing with `Error: Agent prompt '<invalid_agent>' not found.`

Expected: Validation should happen during the "Checking configurations..." phase, before prompting for user input.

## Context & Scope
### Regressing Delta
TBD. Likely an omission in the `start` command's pre-flight check logic.

### Environmental Triggers
Command line usage of `teddy start` with the `-a` or `--agent` flag.

### Ruled Out
TBD.

## Diagnostic Analysis
### Causal Model
1. `handle_new_session` (CLI) calls `_run_cli_preflight_check` which only checks LLM config.
2. It then prints success messages.
3. It calls `user_interactor.ask_question` to get the initial message.
4. ONLY AFTER the user responds, it constructs `SessionOptions` and calls `session_manager.create_session`.
5. `SessionService` (implementing `ISessionManager`) validates the agent name and raises `ValueError`.

### Discrepancies
- Pre-flight check vs. Post-interaction validation. The agent name is available immediately as a CLI flag and should be validated alongside the LLM config.

### Investigation History
1. Initial discovery from user report.
2. MRE confirmed user interaction ("ASK") happens before agent validation.
3. Shadow verification confirmed that moving validation to `_run_cli_preflight_check` prevents the interaction.
4. Regression: `test_session_replan_loop.py` failed because its container setup missed `IPromptManager`.

## Solution
### Root Cause
The `start` command performed LLM configuration checks in a pre-flight step but deferred agent name validation until the `SessionService` was called. The `SessionService` call only occurs *after* the CLI prompts the user for their initial request, leading to a frustrating user experience where a typo in the `-a` flag is only caught after manual input.

### Verified Fix
Modified `_run_cli_preflight_check` in `session_cli_handlers.py` to accept an optional `agent` name. If provided, it uses the `IPromptManager` to verify the prompt existence before the command proceeds to user interaction.

### Systemic Prevention
- Ensure all command-line arguments that can cause a terminal failure are validated in the pre-flight phase.
- Audit other commands (`plan`, `resume`) to ensure they also validate parameters before expensive or interactive operations.
