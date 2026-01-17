# Brief: Generalized Clipboard Output

This document outlines the plan to make "copy to clipboard" a default, generalized behavior for output-producing commands in the `teddy` CLI.

## 1. Problem Definition (The Why)

-   **Goal:** Streamline the interactive workflow between the `teddy` CLI and the AI model by generalizing the existing "copy to clipboard" functionality into a standard, default behavior for all output-producing commands.
-   **User Story:** As a user in an interactive session, when I run a command like `teddy context`, the output should be printed to my console AND copied to my clipboard by default, so I can immediately paste it into my AI prompt without a manual copy step.
-   **Constraint:** The tool must remain functional in non-interactive environments (e.g., CI/CD). This copy-to-clipboard behavior must be suppressible with a `--no-copy` flag.

## 2. Selected Solution (The What)

The selected solution is to reuse and refactor the existing clipboard functionality within the codebase. The `pyperclip` library is already a project dependency and has proven sufficient for the existing use case in the `execute` command. This avoids introducing new external dependencies.

## 3. Implementation Analysis (The How)

The analysis of `packages/executor/src/teddy_executor/main.py` confirmed that clipboard logic is implemented inline within the `execute` command function. The approved technical plan is to refactor this for reusability:

1.  **Create a Helper Function:** Implement a private helper function, `_echo_and_copy(content: str, no_copy: bool = False)`, within `main.py`. This function will encapsulate the logic of printing content to `stdout` and conditionally copying it to the clipboard, failing silently if the clipboard is unavailable.
2.  **Add a CLI Flag:** Introduce a `--no-copy` boolean flag to the `context` and `execute` command signatures using `typer.Option`.
3.  **Refactor Commands:** Update both the `context` and `execute` commands to use the new `_echo_and_copy` helper function, passing the `--no-copy` flag to control its behavior.

## 4. Vertical Slice

- [ ] **Implement Generalized Clipboard Functionality:**
    - [ ] In `packages/executor/src/teddy_executor/main.py`:
        - [ ] Create the private helper function `_echo_and_copy`.
        - [ ] Add the `--no-copy` flag to both the `execute` and `context` command signatures.
        - [ ] Refactor both commands to use the new helper function.
    - [ ] In `README.md`, update the command-line reference table to document the new behavior and the `--no-copy` flag.
