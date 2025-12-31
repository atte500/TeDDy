# Outbound Port: IEnvironmentInspector

**Motivating Vertical Slice:** [Implement `context` Command](../../slices/13-context-command.md)

This port defines the contract for a service that can inspect the local machine's environment to gather information relevant for an AI's context.

## Methods

### `get_environment_info()`

-   **Description:** Retrieves key information about the operating system and the user's current shell environment.
-   **Preconditions:** None.
-   **Postconditions:** A dictionary containing environment details is returned.
-   **Returns:** `dict[str, str]` - A dictionary containing key-value pairs of information, such as `{"os": "darwin", "shell": "/bin/zsh"}`. Expected keys are `os`, `shell`, and `python_version`.
-   **`**Status:**` Planned
