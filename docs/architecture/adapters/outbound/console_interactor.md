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

#### `ask_question(prompt: str) -> str`
The `ask_question` method logic supports both standard input and external editor fallbacks:
1.  **Print Prompt to Stderr:** The prompt is printed to `sys.stderr` to avoid polluting `stdout`. It explicitly offers the user the choice: `Press [Enter] to submit single-line response, or type 'e' + [Enter] to open in Editor:`.
2.  **External Editor Flow ('e'):** If the user types 'e', a temporary markdown file is created. The AI's original prompt is prepended to this file as markdown comments to provide context, followed by instructional comments. The adapter then attempts to launch the user's preferred editor (`$VISUAL` or `$EDITOR`) or falls back to known defaults (`code -w`, `nano`, `vim`). Upon exit, the file is read, instructional comments and the prompt are stripped, and the multiline response is returned.
3.  **Single-Line Standard Input:** If the user does not type 'e', they are opted into standard input. If they typed a response immediately on the first prompt, it is returned. If they just pressed Enter, the adapter reads exactly one more line from standard input. This provides a fast, immediate response mechanism without requiring empty terminating lines.

#### `notify_skipped_action(action: ActionData, reason: str) -> None`
This method prints a formatted, colorized warning to `sys.stderr` when an action is skipped by the orchestrator (e.g., due to a previous failure), ensuring the user is immediately aware of halted execution without needing to inspect the final markdown report.

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

## 4. External Documentation

*   [Python `sys.stdin` documentation](https://docs.python.org/3/library/sys.html#sys.stdin)
