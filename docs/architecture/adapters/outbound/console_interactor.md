# Component Design: ConsoleInteractorAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/console_interactor.py`](/src/teddy_executor/adapters/outbound/console_interactor.py)

## Purpose
Implements the `IUserInteractor` outbound port for the terminal. It renders prompts, plan summaries, diff previews, and handoff requests, then captures the user's responses from `stdin`.

## Consumers
- `ActionExecutor` (`teddy_executor.core.services.action_executor`): Confirms each action before execution through the port.
- [`PromptManager`](../../core/services/prompt_manager.md): Asks the user a free-text question through the port.
- [`ActionPorts`](../../core/domain/action_ports.md): Carries the port into the action layer.
- [CLI Adapter](../inbound/cli.md): Supplies the concrete console interaction for the session and manual flows.

## Dependencies
- [`ISystemEnvironment`](../../core/ports/outbound/system_environment.md): Resolves commands, reads environment variables, launches editors, and manages preview temp files.
- [`IConfigService`](../../core/ports/outbound/config_service.md): Reads the `editor` and `diff_flags` settings.
- **`ConsoleToolingHelper`** (`teddy_executor.adapters.outbound.console_tooling`): Discovers the editor and the diff-viewer command.
- **`ConsoleAskLoop`** (`teddy_executor.adapters.outbound.console_interactor_ask_loop`): Runs the interactive ask loop with the editor fallback. It classifies editors through the shared `core.utils.editor_names` helper, so a launcher wrapper such as `nvim.CMD` takes the synchronous suspend path.
- **`console_interactor_helpers`** (`teddy_executor.adapters.outbound.console_interactor_helpers`): Provides the handoff prompt, the preview-file setup, and the terminal-restore helper.

## Class Invariants
- `stdin_ownership`: Every interactive read runs inside the `stdin_owned()` context so the session quit-key listener backs off.
- `preview_cleanup`: Temporary preview files are deleted in a `finally` block after confirmation.
- `terminal_restore`: The adapter restores the cooked terminal mode before each interaction block and after an external editor exits.
- `stderr_only`: Prompts and messages write to `stderr`, so `stdout` stays reserved for report output.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IUserInteractor`**: The driven contract implemented by this adapter. See the [IUserInteractor design](../../core/ports/outbound/user_interactor.md).

## Data Contracts
- **`Plan`** and **`ActionData`** (`teddy_executor.core.domain.models.plan`): Rendered in the plan summary and the action prompts.
- **`ChangeSet`** (`teddy_executor.core.domain.models.change_set`): Carries the before and after content for the diff previews.
- **`TEDDY_TEST_MOCK_EDITOR_OUTPUT`** (environment variable): Short-circuits the editor with a canned response during tests.

## Operations

### `prompt(text, default="") -> str`
- **Preconditions:** `text` is a non-empty string.
- **Postconditions:** Returns the single-line response, or `default` on empty input. Runs inside `stdin_owned()`.

### `prompt_for_message(initial_message=None) -> Optional[str]`
- **Postconditions:** Returns the editor content. Returns the `TEDDY_TEST_MOCK_EDITOR_OUTPUT` value when that variable is set.

### `ask_question(prompt, resources=None, agent_name=None) -> str`
- **Postconditions:** Prints a cyan `--- MESSAGE from {agent_name} ---` header, the prompt, and any reference files, then returns the response from `ConsoleAskLoop`. Defaults the name to `TeDDy` when `agent_name` is absent.

### `display_message(message) -> None`
- **Postconditions:** Prints the message to the rich console bound to `stderr`.

### `confirm_plan_review(plan) -> bool`
- **Postconditions:** Prints the plan summary and returns `True` when the response starts with `y`. Returns `False` on `EOFError` or `Abort`.

### `confirm_action(action, action_prompt, change_set=None) -> tuple[bool, str]`
- **Postconditions:** Returns `(approved, reason)`. For a `ChangeSet`, it opens the external diff viewer or falls back to the in-terminal preview. The `m` response opens the editor to capture a denial reason. Returns `(False, "Skipped due to non-interactive session.")` on `EOFError` or `Abort`.

### `notify_skipped_action(action, reason) -> None`
- **Postconditions:** Prints a colorized skipped-action warning through `cli_helpers.echo_skipped_action`.

### `notify_warning(message) -> None`
- **Postconditions:** Prints a bold yellow `WARNING:` line to `stderr`.

### `confirm_manual_handoff(action_type, target_agent, resources, message) -> tuple[bool, str]`
- **Postconditions:** Prints the handoff details and returns `(True, "")` on an empty response, or `(False, reason)` on a non-empty response.

### Internal helpers
`_display_ask_header` prints the ask header and reference files. `_launch_editor_synchronous` opens the editor on a temporary file and returns its content. `_handle_external_preview` writes the preview files and launches the diff command in the background.
