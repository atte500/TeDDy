# Vertical Slice: Generalized Clipboard Output

-   **Source Brief:** [../../briefs/02-generalized-clipboard-output.md](./../../briefs/02-generalized-clipboard-output.md)

## 1. Business Goal
To streamline the interactive workflow between the `teddy` CLI and the AI model by making "copy to clipboard" the default, standard behavior for all output-producing commands (like `context` and `execute`). This removes a point of friction for the user, who no longer needs to manually copy-paste output. The functionality must be suppressible for non-interactive scripting environments.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: `context` command defaults to copying output
-   **Given** a user is in an interactive terminal session
-   **When** they run the command `teddy context`
-   **Then** the full project context is printed to standard output
-   **And** the full project context is also copied to the system clipboard
-   **And** a confirmation message (e.g., "Output copied to clipboard.") is printed to standard error.

### Scenario 2: Clipboard behavior is suppressed with a flag
-   **Given** a user or script needs to prevent clipboard interaction
-   **When** they run a command with the suppression flag, such as `teddy context --no-copy` or `teddy --plan-file plan.yaml --no-copy`
-   **Then** the command's primary output (context or report) is printed to standard output as normal
-   **But** the system clipboard is not modified
-   **And** no clipboard-related confirmation message is printed.

## 3. Architectural Changes
The architectural changes for this slice are focused on refactoring the CLI entrypoint to introduce a reusable pattern.
-   `packages/executor/src/teddy_executor/main.py`: This file, which serves as the defacto Inbound CLI Adapter, will be modified to:
    1.  Introduce a new private helper function to handle the "echo and copy" logic.
    2.  Add a `--no-copy` flag to the `context` and `execute` command definitions.
    3.  Refactor the body of both commands to use the new helper function.

## 4. Interaction Sequence
1.  User executes a command (e.g., `teddy context`) with or without the `--no-copy` flag.
2.  The `typer` application in `main.py` parses the command and flags.
3.  The command function calls the relevant core service (`ContextService` or `ExecutionOrchestrator`) to get the primary output string.
4.  The command function passes the output string and the `no_copy` flag to the new `_echo_and_copy` helper.
5.  The helper function prints the output to `stdout` and, if `no_copy` is `False`, attempts to copy the output to the clipboard and print a confirmation to `stderr`.

## 5. Scope of Work

### Step 1: Implement Core Logic in CLI Adapter

-   [ ] **READ:** [CLI Adapter Design Doc](../../adapters/executor/inbound/cli.md)
-   [ ] **IMPLEMENT:** In `packages/executor/src/teddy_executor/main.py`:
    -   [ ] Create a private helper function `_echo_and_copy(content: str, no_copy: bool = False)` that prints the given content to `stdout` and, if `no_copy` is `False`, copies it to the clipboard using `pyperclip`.
    -   [ ] Add the `--no-copy: bool` `typer.Option` to the function signatures of both `execute` and `context`.
    -   [ ] Refactor the `execute` command to replace its inline clipboard logic with a call to `_echo_and_copy`.
    -   [ ] Refactor the `context` command to use the `_echo_and_copy` function for its output.

### Step 2: Update Public Documentation

-   [ ] **IMPLEMENT:** In `README.md`:
    -   [ ] Locate the "Command-Line Reference" table.
    -   [ ] Add a new row or update existing descriptions to document the `--no-copy` flag and explain that output is now copied to the clipboard by default.
