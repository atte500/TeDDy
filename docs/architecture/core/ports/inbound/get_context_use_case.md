# Inbound Port: `IGetContextUseCase`

**Status:** Implemented
**Introduced in:**
- [Slice 13: Implement `context` Command](../../slices/executor/13-context-command.md)
- [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)

## 1. Responsibility

The `IGetContextUseCase` port defines the primary entry point into the application's core logic for gathering project context. It orchestrates the collection of various pieces of information about the project environment and returns them in a structured format.

## 2. Methods

### `get_context`
**Status:** Implemented

*   **Description:** Gathers all project context information, including the repository file tree, system environment details, and the content of specified files.
*   **Signature:** `get_context() -> ContextResult`
*   **Preconditions:** None.
*   **Postconditions:**
    *   Returns a `ContextResult` data transfer object containing the aggregated project context, structured for standardized output.
    *   If `.teddy/global.context` does not exist, it will be created with default content before the context is gathered.

## 3. Data Structures

### `ContextResult`
This is a data transfer object (DTO) that aggregates all the information gathered by the use case.

| Field                 | Type           | Description                                                              |
| --------------------- | -------------- | ------------------------------------------------------------------------ |
| `system_info`         | `dict`         | A dictionary containing system information (e.g., `os`, `cwd`, `shell`). |
| `repo_tree`           | `str`          | A string representing the repository's file and directory structure.     |
| `context_vault_paths` | `list[str]`    | A simple list of file paths gathered from all `.teddy/*.context` files.  |
| `file_contents`       | `dict[str, str | None]`                                                                   | A dictionary mapping file paths to their content, or `None` if the file was not found. |
