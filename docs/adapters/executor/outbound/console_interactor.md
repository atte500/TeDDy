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
The `ask_question` method logic is as follows:
1.  **Print Prompt to Stderr:** The prompt is printed to `sys.stderr` to avoid polluting `stdout`, which is reserved for the final machine-readable report.
2.  **Read Input Loop:** The adapter reads lines from standard input using `input()` until an `EOFError` is caught or the user enters an empty line. This robustly handles both interactive sessions and piped input.
3.  **Return Value:** The collected lines are joined into a single string.

#### `confirm_action(action: 'Action', action_prompt: str) -> tuple[bool, str]`
The `confirm_action` method is responsible for presenting a proposed action to the user and capturing their approval or denial. For `create_file` and `edit` actions, it first presents a visual diff before prompting.

##### Change Preview Logic
Before asking for confirmation on `create_file` or `edit` actions, the adapter will attempt to show a visual diff of the proposed changes. This logic is skipped if the plan is run with auto-approval (`-y`).

1.  **Tool Detection Strategy:** The adapter searches for a diff tool in the following order:
    1.  The command specified in the `TEDDY_DIFF_TOOL` environment variable.
    2.  The Visual Studio Code CLI (`code`) if it's available in the system `PATH`.
    3.  A fallback in-terminal diff rendered using Python's `difflib` module.

2.  **Temporary File Management:**
    *   Two temporary files are created. One holds the original content of the file (or is empty for a `create_file` action), and the other holds the proposed new content.
    *   These files are passed to the selected external diff tool.
    *   They are securely deleted after the diff tool process exits.

3.  **Invocation:** The chosen tool is invoked as a blocking subprocess. Plan execution pauses until the user closes the diff tool. After the tool exits, the standard `(y/n)` confirmation prompt is displayed.

##### Standard Confirmation Logic
1.  **Print Action Prompt:** Display the action description to `sys.stderr` followed by a `(y/n)` query.
2.  **Read Confirmation:** Read a single line of input. The response is considered an approval if it starts with 'y' or 'Y'.
3.  **Prompt for Reason (on denial):** If the action is denied, prompt the user for an optional reason for skipping.
4.  **Return Value:** Return a tuple containing the approval status (`True`/`False`) and the reason string (or an empty string).

```python
# Conceptual Implementation
import sys
import shutil
import subprocess
import tempfile
import difflib
from teddy_executor.core.domain.models.plan import Action # Updated import
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor

class ConsoleInteractorAdapter(IUserInteractor):
    def ask_question(self, prompt: str) -> str:
        # ... (implementation remains the same) ...
        print(prompt, file=sys.stderr, flush=True)
        lines = []
        while True:
            try:
                line = input()
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)

    def _get_diff_command(self) -> list[str] | None:
        # 1. Check for custom tool
        if custom_tool := os.getenv("TEDDY_DIFF_TOOL"):
            return custom_tool.split()
        # 2. Check for VS Code
        if shutil.which("code"):
            return ["code", "--wait", "--diff"]
        # 3. No external tool found
        return None

    def _show_diff(self, action: Action):
        # Logic to get original_content and new_content from action
        # ...

        command = self._get_diff_command()

        if command:
            # Create two temp files
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f_before, \
                 tempfile.NamedTemporaryFile(mode='w+', delete=False) as f_after:
                f_before.write(original_content)
                f_after.write(new_content)
                # ... (close files, get names) ...

            # Launch external tool as subprocess
            subprocess.run(command + [before_path, after_path])

            # ... (cleanup temp files) ...
        else:
            # Fallback to difflib and print to stderr
            diff = difflib.unified_diff(...)
            print("--- Diff ---", file=sys.stderr)
            for line in diff:
                print(line, file=sys.stderr)
            print("------------", file=sys.stderr)


    def confirm_action(self, action: Action, action_prompt: str) -> tuple[bool, str]:
        # Check if action type requires a diff preview
        if action.type in ["create_file", "edit"]:
            self._show_diff(action)

        try:
            prompt = f"{action_prompt}\nApprove? (y/n): "
            response = input(prompt).lower().strip()
            if response.startswith('y'):
                return True, ""

            reason_prompt = "Reason for skipping (optional): "
            reason = input(reason_prompt).strip()
            return False, reason
        except EOFError:
            return False, "Skipped due to non-interactive session."

```

## 4. External Documentation

*   [Python `sys.stdin` documentation](https://docs.python.org/3/library/sys.html#sys.stdin)
