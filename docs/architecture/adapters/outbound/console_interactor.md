# Outbound Adapter: Console Interactor

**Status:** Implemented

## 1. Purpose

The `ConsoleInteractorAdapter` is a concrete implementation of the `IUserInteractor` outbound port. Its responsibility is to handle direct interaction with the user via the standard input/output of the console. It translates the port's abstract request for user input into a specific terminal-based interaction.

## 2. Implemented Ports

*   **Implements:** [`IUserInteractor`](../../contexts/executor/ports/outbound/user_interactor.md)

## 3. Implementation Notes

The `ConsoleInteractorAdapter` depends on the `ISystemEnvironment` outbound port to interact with the host OS, ensuring it remains isolated and testable.

-   **Interactive Diff Previews:** During interactive execution, `create` and `edit` actions provide a visual diff. This feature is configured via a prioritized strategy: the `TEDDY_DIFF_TOOL` environment variable, a fallback to the `code` (VS Code) CLI if present, and a final fallback to an in-terminal view. This provides a better user experience while remaining environment-agnostic.

### Implementation Details

### Implementation Details

#### `ask_question(prompt: str, ...)`
The `ask_question` method implements a non-blocking interaction loop:
1.  **Dynamic Header:** Prints a cyan header: `--- MESSAGE from [AGENT NAME] ---`. Defaults to "TeDDy" if the agent is unknown.
2.  **Non-Blocking Interaction Loop:**
    -   **Trigger Editor ('e'):** Launches the user's preferred editor in the **background** using `ISystemEnvironment.run_command(background=True)`. This immediately returns control to the terminal.
    -   **Terminal Quick-Reply:** Even while the editor is open, the user can type a response directly in the terminal and press Enter to submit it, bypassing the editor.
    -   **Confirm Editor:** If the editor was launched, pressing Enter without a terminal reply signals the adapter to read and return the current content of the temporary file.
3.  **Simplified Empty Confirmation:** If no editor is open and the user presses Enter without typing, the adapter prompts: `Press [Enter] again to confirm empty response`. A second Enter submits an empty string.

#### `notify_skipped_action(action: ActionData, reason: str) -> None`
Delegates terminal output to `cli_helpers.echo_skipped_action` to maintain SLOC compliance.

#### `notify_skipped_action(action: ActionData, reason: str) -> None`
This method prints a formatted, colorized warning to `sys.stderr` when an action is skipped by the orchestrator (e.g., due to a previous failure), ensuring the user is immediately aware of halted execution without needing to inspect the final markdown report.

#### `display_message(message: str) -> None`
Prints a message to standard error. The implementation uses formatting (e.g., Rich tags) to ensure important status information is visually distinct.

#### `confirm_action(action: ActionData, action_prompt: str, change_set: Optional[ChangeSet] = None) -> tuple[bool, str]`
The `confirm_action` method is responsible for presenting a proposed action to the user and capturing their approval or denial. For `CREATE` and `EDIT` actions, it uses a `ChangeSet` to present a visual preview.

##### Change Preview Logic
1.  **Tool Detection:** Precedence: `TEDDY_DIFF_TOOL` env var -> `code` (VS Code) CLI -> In-terminal diff.
2.  **CREATE Actions:** If an external editor is detected, the file is opened as a single-file preview (stripping `--diff` flags). Otherwise, it shows a "New File Preview" in the terminal.
3.  **EDIT Actions:** If an external tool is detected, it shows a split-pane diff. Otherwise, it shows a unified terminal diff.
4.  **Syntax Highlighting:** Temporary files are created preserving the original file's extension (e.g., `.before.py`, `.preview.md`) to enable editor syntax highlighting.
5.  **Lifecycle:** Temporary files are deleted in a `finally` block after user confirmation.

##### Standard Confirmation Logic
1.  **Print Action Prompt:** Display the action description to `sys.stderr` followed by a `(y/n)` query.
2.  **Read Confirmation:** Read a single line of input. The response is considered an approval if it starts with 'y' or 'Y'.
3.  **Prompt for Reason (on denial):** If the action is denied, prompt the user for an optional reason for skipping.
4.  **Return Value:** Return a tuple containing the approval status (`True`/`False`) and the reason string (or an empty string).

#### `confirm_manual_handoff(...) -> tuple[bool, str]`
This method handles the mandatory interruption for `INVOKE` and `RETURN` actions.
1.  **Print Request to Stderr:** Displays a cyan header and a summary of the handoff (target agent, message, and resources).
2.  **Prompt for Approval:** Uses `typer.prompt` to wait for a user response. An empty response (Enter) is an approval. Any non-empty response is treated as a rejection reason.

## 4. External Documentation

*   [Python `sys.stdin` documentation](https://docs.python.org/3/library/sys.html#sys.stdin)
