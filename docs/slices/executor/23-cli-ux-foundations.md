# Vertical Slice: Foundational CLI Additions & Refactoring

*   **Source Brief**: [CLI UX Improvements](./../../briefs/04-cli-ux-improvements.md)

## 1. Business Goal

To provide a convenient way for users to access and override system prompts, and to refactor the user interaction port to prepare for the upcoming visual diff feature. This enhances developer ergonomics by streamlining prompt management and improves system maintainability by setting the foundation for future enhancements.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Get a default prompt
*   **Given:** No local prompt overrides exist in the `.teddy/prompts/` directory.
*   **When:** The user runs the command `teddy get-prompt architect`.
*   **Then:** The content of the default `architect.xml` prompt (from the packaged resources) is printed to the console.
*   **And:** A confirmation message indicates the output has been copied to the clipboard.

### Scenario 2: Get a locally overridden prompt
*   **Given:** A file exists at `.teddy/prompts/architect.md` with the content "local override".
*   **When:** The user runs the command `teddy get-prompt architect`.
*   **Then:** The content "local override" is printed to the console.
*   **And:** A confirmation message indicates the output has been copied to the clipboard.

### Scenario 3: Attempt to get a non-existent prompt
*   **Given:** No default or local prompt named `non-existent-prompt` exists.
*   **When:** The user runs the command `teddy get-prompt non-existent-prompt`.
*   **Then:** An error message "Prompt 'non-existent-prompt' not found." is printed to stderr.
*   **And:** The command exits with a non-zero status code.

### Scenario 4: Use the `--no-copy` flag
*   **Given:** A default prompt `architect` exists.
*   **When:** The user runs the command `teddy get-prompt architect --no-copy`.
*   **Then:** The content of the default `architect` prompt is printed to the console.
*   **And:** No message about copying to the clipboard is displayed.

### Scenario 5: Refactoring does not break existing functionality
*   **Given:** The `confirm_action` method signature has been updated in the `IUserInteractor` port and all implementing adapters.
*   **And:** The call site in `ExecutionOrchestrator` has been updated to pass the full `Action` object.
*   **When:** The full existing test suite is run.
*   **Then:** All tests pass successfully.

## 3. Architectural Changes

The following component documents must be updated to reflect the new requirements of this slice:

*   `docs/adapters/executor/inbound/cli.md`: To document the new `get-prompt` command, its arguments, and behavior.
*   `docs/contexts/executor/ports/outbound/user_interactor.md`: To update the `IUserInteractor` port contract, changing the `confirm_action` method signature.
*   `docs/adapters/executor/outbound/console_interactor.md`: To document the updated method signature in the `ConsoleInteractorAdapter`.
*   `docs/contexts/executor/services/execution_orchestrator.md`: To document the updated call to `confirm_action`.

## 4. Interaction Sequence

### `get-prompt` Command Flow
1.  User executes `teddy get-prompt <prompt_name>`.
2.  The `CLI Adapter` receives the command and its arguments.
3.  The command logic first searches for a custom prompt in the local `./.teddy/prompts/` directory that starts with `<prompt_name>` (e.g., `<prompt_name>.xml`, `<prompt_name>.md`).
4.  If a local file is found, its content is read and returned.
5.  If not found, the logic uses `importlib.resources` to search for a default prompt in the packaged resources with a matching name.
6.  If a packaged prompt is found, its content is read and returned.
7.  If no prompt is found in either location, an error is raised.
8.  The `CLI Adapter` prints the returned content to `stdout` and, by default, copies it to the clipboard, printing a confirmation to `stderr`.

### Refactoring Flow
1.  The `ExecutionOrchestrator` needs to confirm an action with the user.
2.  It invokes `self._user_interactor.confirm_action(action=current_action, action_prompt=prompt_string)`.
3.  The `ConsoleInteractorAdapter` (or any other implementation of `IUserInteractor`) receives the full `Action` object along with the prompt string.
4.  For this slice, the adapter's implementation of `confirm_action` proceeds with the confirmation prompt as it did before, without using the `action` object. The object is passed to prepare for the next slice.

## 5. Scope of Work

This checklist is ordered "outside-in" to guide a logical TDD implementation sequence.

### Part 1: Implement `get-prompt` Command

1.  **`READ` the Design:**
    -   [ ] Read the `[CLI Adapter]` design document: `docs/adapters/executor/inbound/cli.md`.
2.  **`IMPLEMENT` the Command:**
    -   [ ] In `packages/executor/src/teddy_executor/main.py`, add a new `typer` command named `get-prompt`.
    -   [ ] The command must accept a required positional argument `<PROMPT_NAME>` and an optional `--no-copy` flag.
    -   [ ] Implement the logic to search for a prompt file in `./.teddy/prompts/` that starts with `<PROMPT_NAME>`.
    -   [ ] If a local prompt is not found, implement the fallback logic to search for a default prompt in the packaged `prompts/` resources using `importlib.resources`.
    -   [ ] If a prompt is found, use the existing `_echo_and_copy` helper function to print its content to `stdout` and copy it to the clipboard (respecting the `--no-copy` flag).
    -   [ ] If no prompt is found in either location, print an error message to `stderr` and exit with a non-zero status code.

### Part 2: Refactor `IUserInteractor` Port and Implementations

1.  **`READ` the Port Design:**
    -   [ ] Read the `[IUserInteractor]` design document: `docs/contexts/executor/ports/outbound/user_interactor.md`.
2.  **`IMPLEMENT` Port Change:**
    -   [ ] In `packages/executor/src/teddy_executor/core/ports/outbound/user_interactor.py`, update the signature of the `confirm_action` method in the `IUserInteractor` protocol to `confirm_action(self, action: 'Action', action_prompt: str) -> tuple[bool, str]`.
3.  **`READ` the Adapter Design:**
    -   [ ] Read the `[ConsoleInteractorAdapter]` design document: `docs/adapters/executor/outbound/console_interactor.md`.
4.  **`IMPLEMENT` Adapter Change:**
    -   [ ] In `packages/executor/src/teddy_executor/adapters/outbound/console_interactor.py`, update the `ConsoleInteractorAdapter.confirm_action` method signature to match the new protocol.
5.  **`READ` the Service Design:**
    -   [ ] Read the `[ExecutionOrchestrator]` design document: `docs/contexts/executor/services/execution_orchestrator.md`.
6.  **`IMPLEMENT` Service Change:**
    -   [ ] In `packages/executor/src/teddy_executor/core/services/execution_orchestrator.py`, locate the call to `self._user_interactor.confirm_action` and update it to pass the full `action` object as a keyword argument: `action=current_action`.

### Part 3: Acceptance Testing

1.  **`IMPLEMENT` `get-prompt` Tests:**
    -   [ ] Create a new test file: `packages/executor/tests/acceptance/test_cli_ux_improvements.py`.
    -   [ ] Add a test case for Scenario 1: successfully retrieving a default prompt.
    -   [ ] Add a test case for Scenario 2: successfully retrieving a locally overridden prompt.
    -   [ ] Add a test case for Scenario 3: correctly handling a non-existent prompt.
    -   [ ] Add a test case for Scenario 4: verifying the `--no-copy` flag works as expected.
2.  **`VERIFY` Refactoring:**
    -   [ ] Run the entire existing test suite (`poetry -C packages/executor run pytest`) to ensure the refactoring of `confirm_action` has not introduced any regressions.
