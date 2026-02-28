# Outbound Adapter: Console Interactor

**Status:** Implemented

## 1. Purpose

The `ConsoleInteractorAdapter` is a concrete implementation of the `IUserInteractor` outbound port. Its responsibility is to handle direct interaction with the user via the standard input/output of the console. It translates the port's abstract request for user input into a specific terminal-based interaction.

## 2. Implemented Ports

*   **Implements:** [`IUserInteractor`](../../contexts/executor/ports/outbound/user_interactor.md)

## 3. Implementation Notes

The core of this adapter is the logic to read multi-line input from `sys.stdin`. A technical spike was performed to verify the most robust and idiomatic Python pattern for this task.

*   **Spike:** `spikes/technical/10-multiline-input/` (now deleted)
*   **Finding:** The proven approach is to read from `sys.stdin` in a `while` loop, appending lines to a buffer until a blank line (`\n`) or end-of-stream (empty string `''`) is detected.

### Implementation Details

#### `ask_question(prompt: str) -> str`
The `ask_question` method logic supports both standard input and external editor fallbacks:
1.  **Print Prompt to Stderr:** The prompt is printed to `sys.stderr` to avoid polluting `stdout`. It explicitly offers the user the choice: `Press [Enter] to submit single-line response, or type 'e' + [Enter] to open in Editor:`.
2.  **External Editor Flow ('e'):** If the user types 'e', a temporary markdown file is created. The AI's original prompt is prepended to this file as markdown comments to provide context, followed by instructional comments. The adapter then attempts to launch the user's preferred editor (`$VISUAL` or `$EDITOR`) or falls back to known defaults (`code -w`, `nano`, `vim`). Upon exit, the file is read, instructional comments and the prompt are stripped, and the multiline response is returned.
3.  **Single-Line Standard Input:** If the user does not type 'e', they are opted into standard input. If they typed a response immediately on the first prompt, it is returned. If they just pressed Enter, the adapter reads exactly one more line from standard input. This provides a fast, immediate response mechanism without requiring empty terminating lines.

#### `notify_skipped_action(action: ActionData, reason: str) -> None`
This method prints a formatted, colorized warning to `sys.stderr` when an action is skipped by the orchestrator (e.g., due to a previous failure), ensuring the user is immediately aware of halted execution without needing to inspect the final markdown report.

#### `confirm_action(action: ActionData, action_prompt: str) -> tuple[bool, str]`
The `confirm_action` method is responsible for presenting a proposed action to the user and capturing their approval or denial. For `create_file` and `edit` actions, it first presents a visual diff before prompting.

##### Change Preview Logic
Before asking for confirmation on `create_file` or `edit` actions, the adapter will attempt to show a visual diff of the proposed changes. This logic is skipped if the plan is run with auto-approval (`-y`).

1.  **Tool Detection Strategy:** The adapter searches for a diff tool in the following order of precedence:
    1.  A custom tool specified in the `TEDDY_DIFF_TOOL` environment variable. The string is parsed with `shlex` to support commands with arguments (e.g., `"nvim -d"`). If this variable is set but the command is not found in the `PATH`, a warning is printed, and the system falls back directly to the in-terminal diff.
    2.  The Visual Studio Code CLI (`code`) if it's available in the system `PATH`.
    3.  A fallback in-terminal diff rendered using Python's `difflib` module.

2.  **Temporary File Management:**
    *   If an external tool is found, two temporary files are created to hold the "before" and "after" content.
    *   The `confirm_action` method manages the lifecycle of these files, ensuring they are deleted in a `finally` block *after* the user has responded to the confirmation prompt. This prevents "file not found" errors in the diff viewer.

3.  **Invocation:** The chosen external tool is invoked as a **non-blocking** subprocess. The confirmation prompt `(y/n)` is displayed in the terminal immediately, allowing the user to approve or deny the action while the diff is still visible.

##### Standard Confirmation Logic
1.  **Print Action Prompt:** Display the action description to `sys.stderr` followed by a `(y/n)` query.
2.  **Read Confirmation:** Read a single line of input. The response is considered an approval if it starts with 'y' or 'Y'.
3.  **Prompt for Reason (on denial):** If the action is denied, prompt the user for an optional reason for skipping.
4.  **Return Value:** Return a tuple containing the approval status (`True`/`False`) and the reason string (or an empty string).

## 4. External Documentation

*   [Python `sys.stdin` documentation](https://docs.python.org/3/library/sys.html#sys.stdin)
