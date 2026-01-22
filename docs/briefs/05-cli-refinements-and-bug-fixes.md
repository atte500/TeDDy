# Brief: CLI Refinements & Bug Fixes

## 1. Problem Definition (The Why)

The `teddy` CLI executor, while functional, suffers from issues across three key areas that hinder its usability and reliability:

1.  **Reliability & Robustness:** The tool is brittle. It fails on common inputs, such as shell commands containing colons, due to a strict YAML parser (`ScannerError`). Furthermore, its core logic lacks pre-validation; it asks for user approval on actions that are destined to fail (e.g., an `edit` where the `find` block doesn't match the file's content), leading to a frustrating "approve-then-fail" loop and inaccurate diff previews.

2.  **Developer Experience (DX):** The interactive experience feels unpolished. Key outputs like diffs are difficult to parse without color-coding. Previews for complex actions (`create_file`, `chat_with_user`) are crammed into the terminal instead of using a proper editor, making them hard to review. The approval prompts themselves are often verbose and show unnecessary detail.

3.  **Configuration & Flexibility:** The tool's configuration is rigid. Relying solely on environment variables (`TEDDY_DIFF_TOOL`) prevents project-specific setups, forcing users to manage global settings for different contexts.

## 2. Selected Solution (The What)

### Theme 1: Critical Bug Fixes
*   **YAML Parsing:** The `PlanParser.parse` method in `plan_parser.py` will be modified. Before calling `yaml.safe_load`, it will pre-process the raw `plan_content` string. A generic regular expression will be used to find any key-value line where the value is a single line, contains a colon (`:`), and is not already quoted. It will wrap that value in double quotes, making the parsing robust to special characters.
*   **`description` in Report:**
    1.  The `ActionLog` dataclass in `execution_report.py` will be updated to include an optional `description` field: `description: Optional[str] = None`.
    2.  The `ActionDispatcher.dispatch_and_execute` method in `action_dispatcher.py` will be modified to accept the full `ActionData` object. It will then pass the `action_data.description` into the `ActionLog` it constructs.
    3.  The `CliFormatter` will automatically pick up the new field, so no changes are needed there.
*   **URL `read`:**
    1.  The specific `ReadAction` handler class (managed by the `ActionFactory`) will be modified to accept both `IFileSystemManager` and `IWebScraper` in its constructor.
    2.  Its `execute` method will be updated to check if the `path` parameter starts with `http://` or `https://`. If it does, it will call the web scraper; otherwise, it will call the file system manager.
    3.  The `ActionFactory` will be updated to inject both dependencies into the `ReadAction` handler upon creation.
    4.  The composition root in `main.py` will be updated to provide the `WebScraperAdapter` to the `ActionFactory`.

### Theme 2: Action Robustness & Pre-validation
*   **Problem:** The current implementation performs validation *after* the user approves an action. This leads to a poor user experience where a user can approve an invalid action, only to see it fail. Furthermore, the diff preview logic in `ConsoleInteractor` is a simplistic reimplementation of the `edit` logic and does not match the robust, indentation-aware logic in `LocalFileSystemAdapter`, causing inconsistent diffs.
*   **Solution:** A "dry run" or "preview" capability will be introduced to unify validation and diff generation.
    1.  The `IFileSystemManager` port will be extended with two new methods: `preview_create(path, content)` and `preview_edit(path, find, replace)`. These methods will perform all validation and, if successful, return the predicted content of the file *after* the change without writing to disk.
    2.  The `LocalFileSystemAdapter` will implement these new preview methods by reusing its existing robust, indentation-aware validation and text replacement logic, ensuring consistency between the preview and the final output.
    3.  The `ConsoleInteractorAdapter.confirm_action` method will be refactored. Before showing any prompt or diff, it will call the appropriate preview method. If the method raises a validation error (e.g., `FileAlreadyExistsError`, `SearchTextNotFoundError`), the error will be caught, displayed to the user, and the action will be rejected without a prompt.
    4.  If the preview method succeeds, its return value (the "after" content) will be used to generate a perfectly accurate diff for the user.

### Theme 3: Core UX Enhancements
*   **File-based Previews:**
    *   **`CREATE` action:** In `ConsoleInteractorAdapter.confirm_action`, the logic for `create_file` actions will be changed. Instead of generating a diff, it will write the action's `content` to a temporary file and use the existing external tool logic (e.g., VS Code) to open this single file for preview. The in-terminal fallback will simply print the content.
    *   **`CHAT_WITH_USER` action:** The `ConsoleInteractorAdapter.ask_question` method will be refactored. It will write the `prompt` string to a temporary file (e.g., `prompt.md`) and open it in an editor. This allows for better readability of complex, multi-line prompts. After the editor is closed, the user will be prompted for their response in the terminal as usual.
*   **Simplified Approval Prompt:** The prompt-building logic within `ExecutionOrchestrator` will be modified. It will construct a cleaner, more summarized view of the action, showing only the most relevant parameters (e.g., `path` and `description` for file operations, `command` for `execute`, `queries` for `research`).
*   **Open File After Action:** This feature will be implemented as follows:
    1.  A new method, `open_file_in_editor(path: str)`, will be added to the `IUserInteractor` port.
    2.  `ConsoleInteractorAdapter` will implement this method, using the same `_get_diff_viewer_command` logic to find an appropriate editor (e.g., `code`) and open the specified file path.
    3.  In `ExecutionOrchestrator`, after an action is successfully dispatched, it will check if the action was a `create_file` or `edit` and if a new (to be defined in Theme 4) configuration flag `open_after_action` is true. If both are true, it will call the new `self._user_interactor.open_file_in_editor()` method with the file path.

### Theme 4: Configuration & Polish
*   **Local Configuration:** A new `ConfigService` will be created. It will read settings from a project-specific `.teddy/config.yaml` file, falling back to environment variables if the file or key does not exist. The `ConsoleInteractorAdapter` will be injected with this service to retrieve `TEDDY_DIFF_TOOL`. The `ExecutionOrchestrator` will also use this service to check for the new `open_after_action` flag.
*   **UI Polish:**
    *   **Colorized Diff:** The `_show_in_terminal_diff` method in `ConsoleInteractorAdapter` will be updated. It will loop through the lines from the `difflib` generator and wrap them in ANSI escape codes: green for lines starting with `+`, red for `-`, and cyan for `@@`.
    *   **One-Time Hint:** A new instance variable, `_diff_hint_shown = False`, will be added to `ConsoleInteractorAdapter`. Inside `_show_in_terminal_diff`, a check `if not self._diff_hint_shown:` will be added. If true, a hint about configuring an external diff tool will be printed to `stderr`, and the flag will be set to `True`.

## 3. Implementation Analysis (The How)

The implementation will be driven by outside-in acceptance tests. The core of this work involves modifying the adapters to be smarter and more user-friendly, while extending the core ports to support these new capabilities.

The most critical change is refactoring `ConsoleInteractorAdapter` to delegate all pre-action validation and content prediction to `IFileSystemManager`. This correctly separates concerns, eliminates duplicated (and flawed) logic, and ensures that the user's preview is identical to the final result. The existing robust, indentation-aware `edit` logic within `LocalFileSystemAdapter` is the key enabler for this and will be reused for the `preview_edit` method.

## 4. Vertical Slices

-   [ ] **Slice 1: Implement Theme 1 (Critical Bug Fixes).**
    -   [ ] **YAML Parsing:** Add a failing acceptance test for unquoted commands with colons, then implement the regex-based pre-processing fix in `PlanParser`.
    -   [ ] **`description` Field:** Add `description` to the `ActionLog` model. Update `ActionDispatcher` to populate this field. Add a failing acceptance test to verify the `description` appears in the final report.
    -   [ ] **URL `read`:** Add a failing acceptance test for reading a URL. Modify the `ReadAction` handler to delegate to the correct adapter. Update the `ActionFactory` and composition root to inject the `WebScraperAdapter`.

-   [ ] **Slice 2: Implement Theme 2 (Action Robustness & Pre-validation via "Dry Run").**
    -   [ ] **Port/Adapter:** Extend the `IFileSystemManager` port and `LocalFileSystemAdapter` with `preview_create` and `preview_edit` methods that perform validation and return the predicted file content.
    -   [ ] **Interactor:** Refactor `ConsoleInteractorAdapter.confirm_action` to use the new preview methods. It must catch validation errors and display them to the user *instead of* the approval prompt. It must use the returned content to generate the diff.
    -   [ ] **Acceptance Tests:** Add acceptance tests to verify that invalid `CREATE` and `EDIT` actions now fail *before* the approval prompt is shown. Also, add a test to confirm that an indentation-robust edit shows a correct diff preview.

-   [ ] **Slice 3: Implement Theme 3 (Core UX Enhancements).**
    -   [ ] **Config Service:** Create a new `ConfigService` that reads a `.teddy/config.yaml` file. Inject this service into `ConsoleInteractorAdapter` and update it to check the config for `TEDDY_DIFF_TOOL` before checking the environment variable.
    -   [ ] **File-based Previews:** Refactor `ConsoleInteractorAdapter` to change the preview mechanism for `create_file` and `chat_with_user` actions to use temporary files opened in an external editor.
    -   [ ] **Simplified Prompt:** Update the prompt generation logic in `ExecutionOrchestrator` to produce a summarized, context-aware prompt for user approval.
    -   [ ] **Open After Action:** Add the `open_file_in_editor` method to the `IUserInteractor` port and its implementation. Add the logic to `ExecutionOrchestrator` to call this method after successful file modification actions (contingent on a config flag).

-   [ ] **Slice 4: Implement Theme 4 (Configuration & Polish).**
    -   [ ] **Colorized Diff:** Modify the `_show_in_terminal_diff` method in `ConsoleInteractorAdapter` to print lines with ANSI color codes (`+` for green, `-` for red).
    -   [ ] **One-Time Hint:** Add state to `ConsoleInteractorAdapter` to track if the diff tool hint has been shown, and display it once when the in-terminal diff is used for the first time.
