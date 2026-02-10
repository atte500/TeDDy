# Implement Smart Adapter and `stdin` Feature

## 1. Business Goal
The `teddy` executor currently has two major operational limitations that cause AI-generated plans to fail frequently:
1.  **Shell Parsing Failures:** `EXECUTE` actions with multi-line string arguments, most notably `git commit -m "..."`, are misinterpreted by the shell and fail.
2.  **Filesystem Sandboxing:** An `EXECUTE` action runs in an isolated sandbox and cannot access files created by a `CREATE` action within the same plan, making multi-step file processing impossible in a single turn.

The goal of this slice is to solve both of these problems to make the executor more robust, capable, and reliable. We will implement a two-pronged solution:
1.  **A "Smart Adapter" for Git Commits:** The `ShellAdapter` will be enhanced to transparently fix multi-line `git commit -m` commands, requiring zero changes to how the AI generates plans.
2.  **A `stdin` Feature for `EXECUTE`:** The `EXECUTE` action will be enhanced with a new `stdin` parameter, providing a universal, robust pattern for piping data to any command-line tool and bypassing the filesystem sandbox.

## 2. Architectural Changes
-   **`ActionData` Model (`domain/models/plan.py`):** The `ActionData` class will be modified to include a new optional field: `stdin: Optional[str] = None`.
-   **`MarkdownPlanParser` (`services/markdown_plan_parser.py`):** The parser will be enhanced to recognize and parse an optional `stdin` block within an `EXECUTE` action. This block will be a fenced code block similar to the `command`.
-   **`ShellAdapter` (`adapters/outbound/shell_adapter.py`):** The `execute` method will be refactored to:
    1.  Implement a "Smart Router" that checks if the command is `git commit -m`. If so, it will transform the command into `git commit -F -` and move the message content to the `stdin` parameter for processing.
    2.  If an `stdin` parameter is present (either from the original plan or the Smart Router), it will be passed to the `subprocess.run` call's `input` argument, with `text=True`.

## 3. Scope of Work

-   **[ ] 1. Acceptance Tests:**
    -   In a new test file, write a failing acceptance test for the "transparent `git commit` fix" scenario.
    -   Write a second failing acceptance test for the "general `stdin`" scenario (e.g., piping JSON to `jq .`).
-   **[ ] 2. Domain Model:**
    -   Add the `stdin` field to the `ActionData` class.
-   **[ ] 3. Parser Implementation:**
    -   Update `_parse_execute_action` in `MarkdownPlanParser` to look for and parse a `stdin` code block.
    -   Add a unit test to `test_markdown_plan_parser.py` to verify the new parsing logic.
-   **[ ] 4. Adapter Implementation:**
    -   Refactor the `ShellAdapter` to implement the "Smart Router" and `stdin` piping logic.
    -   Add unit/integration tests to `test_shell_adapter.py` to cover the new logic.
-   **[ ] 5. Verification:**
    -   Ensure all new and existing tests pass, including the acceptance tests created in step 1.
-   **[ ] 6. Documentation:**
    -   Update `docs/ARCHITECTURE.md` to document the new `stdin` feature and the `ShellAdapter`'s "Smart Router" behavior as a Key Architectural Decision.

## 4. Acceptance Criteria

### Scenario: Transparently fix a multi-line git commit
-   **Given** a plan containing an `EXECUTE` action with the command `git commit -m "feat: Add new feature\n\nImplement the core logic."`
-   **When** the user runs `teddy execute`.
-   **Then** the command should succeed.
-   **And** a git commit should be created in the repository with the title "feat: Add new feature" and the body "Implement the core logic.".

### Scenario: Process data using `stdin`
-   **Given** a plan containing an `EXECUTE` action with the command `jq .` and an `stdin` block containing `{"key": "value"}`.
-   **When** the user runs `teddy execute`.
-   **Then** the command should succeed.
-   **And** the `stdout` of the action should be the formatted JSON string `{\n  "key": "value"\n}`.
