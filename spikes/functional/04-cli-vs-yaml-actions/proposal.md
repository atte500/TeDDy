# Proposal: Distinguishing CLI Commands from YAML Actions

This document clarifies the roles of the `teddy` CLI commands (`context`, `copy-unstaged`) and their relationship to YAML actions.

## Principle

**CLI commands are for the User.** They are imperative tools for the human operator to interact with their local environment and prepare information for the AI.

**YAML actions are for the AI.** They are declarative instructions that form a plan to be executed by the `teddy` tool.

## Proposed Separation of Concerns

1.  **`context` Command**
    *   **`teddy context` (CLI):** When a user runs this, it gathers project information (like `repotree`). Its output is **printed to the console AND copied to the clipboard** for the user to easily paste to the AI.
    *   **`action: context` (YAML):** This action is **disallowed** in YAML plans.

2.  **`copy-unstaged` Command**
    *   **`teddy copy-unstaged` (CLI):** When a user runs this, it executes `git diff` to capture unstaged changes. The output is **printed to the console AND copied to the clipboard**.
    *   **`action: copy-unstaged` (YAML):** This action is **disallowed** in YAML plans.

## Summary Table

The `teddy` tool has two modes of operation: direct CLI commands for the user, and plan execution for the AI.

| Name             | User CLI Command? | AI Plan Action? | Purpose                                           |
| ---------------- | :---------------: | :-------------: | ------------------------------------------------- |
| `context`        |         ✅         |        ❌        | User gathers project info for the AI.             |
| `copy-unstaged`  |         ✅         |        ❌        | User copies git diff to the clipboard for the AI. |
| `read`           |         ❌         |        ✅        | Plan instruction to read a file/URL.              |
| `edit`           |         ❌         |        ✅        | Plan instruction to modify a file.                |
| `execute`        |         ❌         |        ✅        | Plan instruction to run a shell command.          |
| `research`       |         ❌         |        ✅        | Plan instruction to perform a web search.         |
| `chat_with_user` |         ❌         |        ✅        | Plan instruction to prompt the user for input.    |
| `create_file`    |         ❌         |        ✅        | Plan instruction to create a new file.            |
