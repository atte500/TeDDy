# Inbound Port: IGetContextUseCase

**Motivating Vertical Slice:** [Implement `context` Command](../../slices/13-context-command.md)

This port defines the primary entry point for the use case of gathering a comprehensive snapshot of the project's context for an AI.

## Methods

### `get_context()`

-   **Description:** Orchestrates the collection of all context information, including the repository tree, environment details, and the contents of all files specified in the context lists. It also handles the initial setup of the `.teddy` configuration directory if it doesn't exist.
-   **Preconditions:** The command must be run from within a valid directory.
-   **Postconditions:** A `ContextResult` object containing the full project context is returned. If the `.teddy` directory or its files did not exist, they are created.
-   **Returns:** A `ContextResult` domain object.
-   **`**Status:**` Planned

## Data Structures

### `ContextResult`

This is a data structure (likely a dataclass) that aggregates all the information gathered during the use case.

-   `repo_tree`: `str` - The file and directory structure of the repository, ignoring paths from `.gitignore`.
-   `environment_info`: `dict[str, str]` - Key-value pairs of OS and terminal information (e.g., `{"os": "darwin", "shell": "/bin/zsh"}`).
-   `main_gitignore_content`: `str | None` - The content of the root `.gitignore` file, or `None` if it doesn't exist.
-   `file_contexts`: `list[FileContext]` - A list containing the content of each requested file.
-   `permanent_context_files`: `list[str]` - The list of file paths from the permanent context file.
-   `ai_context_files`: `list[str]` - The list of file paths from the AI-managed context file.

### `FileContext`

-   `file_path`: `str` - The path to the file.
-   `content`: `str | None` - The content of the file, or `None` if the file was not found.
-   `status`: `str` - The status of the file read operation (e.g., "found", "not_found").
