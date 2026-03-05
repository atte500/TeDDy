# Inbound Port: `IInitUseCase`

**Status:** Implemented
**Introduced in:** [Slice 09-02: Auto-Initialization](../../../project/slices/09-02-auto-initialization.md)

## 1. Responsibility

The `IInitUseCase` port defines the inbound interface for ensuring a project is correctly initialized with the required TeDDy configuration and context files. This port is intended to be called by the CLI entry point before any other commands are executed.

## 2. Methods

### `ensure_initialized`
*   **Description:** Ensures the `.teddy/` directory and its essential configuration files are present in the current working directory.
*   **Signature:** `ensure_initialized() -> None`
*   **Postconditions:**
    *   A `.teddy/` directory exists in the current project root.
    *   A `.teddy/.gitignore` file exists, configured to ignore the directory's contents.
    *   A `.teddy/config.yaml` file exists with default template content.
    *   A `.teddy/init.context` file exists with default template content.
    *   Existing files are NEVER overwritten.
