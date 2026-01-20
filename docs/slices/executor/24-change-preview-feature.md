# Vertical Slice: Implement Change Preview Feature

*   **Source Brief:** [CLI UX Improvements](../briefs/04-cli-ux-improvements.md)

## 1. Business Goal

To improve the interactive plan approval workflow by providing users with an immediate, visual diff of proposed changes for `create_file` and `edit` actions. This will make approvals faster, reduce cognitive load, and increase user confidence by leveraging familiar external tools like VS Code or a user-configured diff tool.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Custom Diff Tool is Used
*   **Given** the `TEDDY_DIFF_TOOL` environment variable is set to a valid command (e.g., `meld`).
*   **When** an interactive plan containing a `create_file` or `edit` action is executed.
*   **Then** the executor should invoke the specified custom diff tool to display the changes before prompting for confirmation.
*   **And** the plan execution should pause until the diff tool process is closed.

*Example:*
```gherkin
Given the environment variable TEDDY_DIFF_TOOL is set to "meld"
When I run a plan with an `edit` action interactively
Then the command "meld <temp_file_before> <temp_file_after>" is executed
And I am prompted for approval after closing meld
```

### Scenario 2: VS Code is Used as a Fallback
*   **Given** the `TEDDY_DIFF_TOOL` environment variable is NOT set.
*   **And** the `code` command-line tool is available in the system's `PATH`.
*   **When** an interactive plan containing a `create_file` or `edit` action is executed.
*   **Then** the executor should invoke `code --diff` to display the changes in Visual Studio Code.
*   **And** the plan execution should pause until the diff tab is closed.

*Example:*
```gherkin
Given the environment variable TEDDY_DIFF_TOOL is not set
And the command "code" is available
When I run a plan with a `create_file` action interactively
Then the command "code --wait --diff <temp_file_before> <temp_file_after>" is executed
And I am prompted for approval after closing the diff in VS Code
```

### Scenario 3: In-Terminal Diff is Used as a Final Fallback
*   **Given** the `TEDDY_DIFF_TOOL` environment variable is NOT set.
*   **And** the `code` command-line tool is NOT available in the system's `PATH`.
*   **When** an interactive plan containing a `create_file` or `edit` action is executed.
*   **Then** the executor should print a unified diff directly to the terminal using Python's `difflib`.
*   **And** it should then prompt the user for confirmation.

*Example:*
```gherkin
Given the environment variable TEDDY_DIFF_TOOL is not set
And the command "code" is not available
When I run a plan with an `edit` action interactively
Then a diff output is printed to the console
And I am then prompted for approval
```

### Scenario 4: No Diff is Shown for Auto-Approved Plans
*   **Given** any diff tool configuration.
*   **When** a plan is executed with the `--yes` (or `-y`) auto-approval flag.
*   **Then** no diff tool should be launched and no in-terminal diff should be printed.
*   **And** the action should be executed without prompting for confirmation.

## 3. Architectural Changes

-   **`ConsoleInteractorAdapter`:** This adapter will be modified to house the new preview logic within its `confirm_action` method.

## 4. Interaction Sequence

1.  The `ExecutionOrchestrator` calls `IUserInteractor.confirm_action`, passing the full `Action` object.
2.  The `ConsoleInteractorAdapter.confirm_action` method checks if the action type is `create_file` or `edit`.
3.  If it is, the adapter implements the tool detection strategy:
    1.  Check for `TEDDY_DIFF_TOOL` environment variable.
    2.  If not found, check for the `code` command using `shutil.which()`.
    3.  If neither is found, select the internal `difflib` fallback.
4.  The adapter creates temporary files representing the state of the file before and after the proposed change. For a `create_file` action, the "before" state is an empty file.
5.  The adapter invokes the selected tool (`TEDDY_DIFF_TOOL`, `code`, or `difflib`) as a subprocess.
6.  After the diff view is closed by the user, the adapter proceeds to prompt for `y/n` confirmation as usual.
7.  The user's response is returned to the orchestrator.

## 5. Scope of Work

This checklist guides the implementation of the change preview feature in an "outside-in" manner, starting with the adapter's public contract and ending with verification through acceptance tests.

### `ConsoleInteractorAdapter`
1.  **READ:** The updated design document for the `ConsoleInteractorAdapter` to understand the full requirements for the change preview logic.
    - `docs/adapters/executor/outbound/console_interactor.md`
2.  **IMPLEMENT:** The change preview logic within the `confirm_action` method of the `ConsoleInteractorAdapter`.
    -   Target file: `packages/executor/src/teddy_executor/adapters/outbound/console_interactor.py`
    -   Implement the tool detection strategy (`TEDDY_DIFF_TOOL` > `code` > `difflib`).
    -   Add logic to create, use, and clean up temporary files for the external diff tool.
    -   Ensure the standard `(y/n)` prompt is displayed *after* the preview is shown and closed.
    -   This logic should only trigger for `create_file` and `edit` actions and should be skipped when the `-y` flag is used.

### Acceptance Tests
1.  **CREATE:** A new acceptance test file to verify the change preview feature.
    -   File: `packages/executor/tests/acceptance/test_change_preview_feature.py`
2.  **IMPLEMENT:** The following test cases:
    -   A test that verifies the custom tool specified in `TEDDY_DIFF_TOOL` is called correctly. Use mocking to assert that `subprocess.run` is called with the expected command.
    -   A test that verifies `code --diff` is called when `TEDDY_DIFF_TOOL` is not set but `shutil.which('code')` returns a path.
    -   A test that verifies the `difflib` output is printed to the console when no external tool is found.
    -   A test that confirms no diff is shown when the `-y` flag is passed to the CLI.
