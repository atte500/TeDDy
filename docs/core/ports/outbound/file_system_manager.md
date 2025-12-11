# Outbound Port: `FileSystemManager`

**Introduced in:** [Slice 02: Implement `create_file` Action](../../slices/02-create-file-action.md)

## 1. Responsibility

The `FileSystemManager` port defines a technology-agnostic interface for interacting with a file system. It provides methods for common file operations like creating, reading, and updating files, abstracting the details away from the application's core logic.

## 2. Methods

### `create_file`

*   **Description:** Creates a new file at a specified path with the given content. The operation must be atomic. The parent directory is assumed to exist.
*   **Signature:** `create_file(path: str, content: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   No file must exist at the specified `path`.
*   **Postconditions:**
    *   On success, a new file is created at `path` containing the exact `content`.
    *   If a file already exists at `path`, a `FileExistsError` (or a custom domain equivalent) must be raised.

### `read_file`

*   **Description:** Reads the entire content of a file at a specified path.
*   **Signature:** `read_file(path: str) -> str`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   A file must exist at the specified `path`.
*   **Postconditions:**
    *   On success, returns the full string content of the file.
    *   If no file exists at `path`, a `FileNotFoundError` (or a custom domain equivalent) must be raised.

## 3. Related Spikes

*   N/A
