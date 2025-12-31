# Outbound Port: IRepoTreeGenerator

**Motivating Vertical Slice:** [Implement `context` Command](../../slices/13-context-command.md)

This port defines the contract for a service that can generate a textual representation of the repository's directory and file structure. This is a crucial component for providing context to an AI.

## Methods

### `generate_tree()`

-   **Description:** Scans the current working directory and its subdirectories to build a tree-like string representation. The implementation **must** respect the ignore patterns defined in any `.gitignore` files found in the repository. It should also ignore common noise directories like `.git`, `.vscode`, and `__pycache__` by default.
-   **Preconditions:** None.
-   **Postconditions:** A string containing the formatted repository tree is returned.
-   **Returns:** `str` - The repository tree as a multi-line string.
-   **`**Status:**` Planned
