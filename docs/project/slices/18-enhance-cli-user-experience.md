# Slice: Enhance CLI User Experience

## 1. Business Goal
To improve the ergonomics and transparency of the TeDDy CLI by providing a robust multiline input mechanism for the `CHAT_WITH_USER` action and ensuring skipped actions clearly communicate their status to the console.

## 2. Acceptance Criteria
*   **Scenario: Multiline Chat Input**
    *   **Given** a plan with a `CHAT_WITH_USER` action is executed interactively.
    *   **When** the CLI prompts for input.
    *   **Then** the user is presented with an option: `Press [Enter] for single-line input, or type 'e' to open in Editor:`
    *   **If** the user types `e`, the CLI opens a temporary markdown file in the editor specified by `$VISUAL`, `$EDITOR`, or falls back to VS Code/nano/vim.
    *   **When** the user saves and closes the editor, the CLI reads the content, ignoring instructional comments.
*   **Scenario: Orchestrator Console Warnings**
    *   **Given** an executing plan where an action fails.
    *   **When** the `ExecutionOrchestrator` skips the subsequent actions.
    *   **Then** the `ConsoleInteractor` must print a clear, colorized warning to `stderr` for each skipped action (e.g., `[SKIPPED] CHAT_WITH_USER: Skipped because a previous action failed.`).

## 3. User Showcase
1.  Run a plan containing a `CHAT_WITH_USER` action.
2.  When prompted, type `e` and press enter.
3.  Your default text editor should open a temporary file. Type a multi-line response, save, and exit.
4.  Verify the CLI correctly captured the multi-line input and continued execution.
5.  Create a plan with a failing `EXECUTE` action followed by a `CHAT_WITH_USER` action. Execute it. Verify the console prints a yellow warning indicating the chat action was skipped.

## 4. Architectural Changes
*   **`ConsoleInteractorAdapter`:** Update `ask_question` to implement the external editor logic, utilizing `tempfile` and `subprocess`. Add a new method `notify_skipped_action(action: ActionData, reason: str)` to handle printing skip warnings.
*   **`IUserInteractor`:** Add the `notify_skipped_action` method to the interface.
*   **`ExecutionOrchestrator`:** Update the `execute` loop. When an action is skipped due to `halt_execution = True`, call `self._user_interactor.notify_skipped_action`.

## 5. Scope of Work
- [ ] Update `IUserInteractor` interface in `src/teddy_executor/core/ports/outbound/user_interactor.py`.
- [ ] Implement `notify_skipped_action` in `ConsoleInteractorAdapter`.
- [ ] Update `ExecutionOrchestrator` to call `notify_skipped_action` when `halt_execution` is true.
- [ ] Implement the external editor fallback logic in `ConsoleInteractorAdapter.ask_question`. Ensure it strips instructions (e.g., `# --- Please enter your response above this line ---`).
- [ ] Write unit tests for `ConsoleInteractorAdapter` testing both single-line and multiline editor fallback logic.
- [x] Write integration/acceptance tests verifying the new orchestrator skip warning behavior.

## Implementation Notes
- **External Editor Lookup:** The `ConsoleInteractorAdapter.ask_question` method correctly respects `$VISUAL` and `$EDITOR` before falling back to `code -w`, `nano`, and `vim`. The `subprocess.run` command correctly utilizes `shlex.split` to ensure editors with arguments (like `code -w`) launch correctly.
- **Strict Error Handling:** If the editor process fails or no editor can be found, the system gracefully prints an error to stderr and falls back immediately to the standard input reading loop, preventing the CLI from crashing.
- **Testing Approach:** Acceptance tests for the interactive editor use `monkeypatch` on `subprocess.run` to simulate an external editor modifying the temporary file, ensuring end-to-end functionality without hanging CI.
