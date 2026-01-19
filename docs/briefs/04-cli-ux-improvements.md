# Brief: CLI UX Improvements

This document defines the scope and technical approach for implementing key user experience enhancements in the `teddy` CLI.

## 1. Problem Definition (The Why)

The `teddy` executor's interactive workflow can be improved to reduce user friction and enhance usability.

1.  **Lack of Visual Diffs:** When approving `edit` and `create` actions, the user must mentally parse text blocks in the terminal. The goal is to provide an immediate, visual diff in a familiar editor (like VS Code) to make approvals faster and more confident.
    *   **Constraint:** This should be the default behavior, only skipped when a plan is auto-approved via the `-y` flag. The feature is dependent on a command-line diff tool being available in the user's `PATH`.

2.  **Inconvenient and Inflexible Access to System Prompts:** Users need a convenient way to access system prompts and to customize or override them for specific projects.
    *   **Goal:** Create a `get-prompt <prompt_name>` command that outputs a specific prompt's content to the console.
    *   **Constraint:** The command must implement an override system. It should first search for the prompt in a local `.teddy/prompts/` directory and, if not found, fall back to the default prompts packaged with the application.

## 2. Selected Solution (The What)

### Feature: Enhanced Change Previews

The core logic will check for a diff tool before prompting the user for approval for `create` and `edit` actions.

*   **Tool Detection Strategy (in order of priority):**
    1.  Check for a user-defined tool in the `TEDDY_DIFF_TOOL` environment variable.
    2.  If not set, check for the VS Code `code` command using `shutil.which('code')`.
    3.  If neither is found, fall back to an in-terminal diff using Python's `difflib` module.
    4.  If a tool is found (steps 1 or 2), it will be used to open a visual diff. The plan will create temporary files to pass to the diff command.

### Feature: `get-prompt` Command

A new CLI command `teddy get-prompt <prompt_name>` will be added.

*   **Logic:**
    1.  It will search for a custom prompt in `<current_directory>/.teddy/prompts/` that starts with `<prompt_name>`, ignoring the file extension.
    2.  If not found, it will use `importlib.resources` to search for a default prompt in the packaged `prompts/` directory, again ignoring the extension.
    3.  The content of the found prompt will be output. Consistent with existing commands like `context`, the output will be copied to the clipboard by default. This can be disabled with a `--no-copy` flag.

## 3. Implementation Analysis (The How)

The implementation will be broken into two parts, starting with a necessary refactoring.

1.  **Refactor the `IUserInteractor` Port:** The `confirm_action` method signature in the port and all implementing classes will be changed from `confirm_action(self, action_prompt: str)` to `confirm_action(self, action: 'Action', action_prompt: str)`. The single call site in `ExecutionOrchestrator` will be updated to pass the full `action` object.

2.  **Implement Preview Logic:** The logic will be added to `ConsoleInteractorAdapter.confirm_action`. It will inspect the `action.type`. If it is `create_file` or `edit`, it will execute the tool detection strategy. Based on the outcome, it will either call an external diff tool via `subprocess.run()` with temporary files or print an in-terminal diff using `difflib`.

3.  **Implement `get-prompt` Command:** A new command will be added to `main.py`, following the pattern of the existing `context` command. It will implement the specified file search logic (local override first, then packaged resources) and use the existing `_echo_and_copy` helper to handle output.

## 4. Vertical Slices

-   [ ] **Slice 1: Foundational CLI Additions & Refactoring.**
    -   [ ] Implement the `get-prompt` command in `main.py` with local override and packaged resource fallback logic.
    -   [ ] Add acceptance tests for the `get-prompt` command.
    -   [ ] Refactor the `confirm_action` method signature in `IUserInteractor` and `ConsoleInteractorAdapter` to accept an `Action` object.
    -   [ ] Update the call site in `ExecutionOrchestrator` to pass the `Action` object.
    -   [ ] Ensure all existing tests pass after the refactoring.

-   [ ] **Slice 2: Implement Change Preview Feature.**
    -   [ ] In `ConsoleInteractorAdapter`, implement the full preview logic:
        -   Detect `TEDDY_DIFF_TOOL` environment variable.
        -   Detect `code` command-line tool.
        -   Fall back to an in-terminal `difflib` view.
    -   [ ] Add logic to create and manage temporary files for diffing.
    -   [ ] Add acceptance tests covering all three preview scenarios (custom tool, vscode, difflib fallback).
