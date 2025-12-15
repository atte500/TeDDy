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

### `edit_file`
**Introduced in:** [Slice 06: Implement `edit` Action](../../slices/06-edit-action.md)

*   **Description:** Finds and replaces the first occurrence of a specific string within a file.
*   **Signature:** `edit_file(path: str, find: str, replace: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   A file must exist at the specified `path`.
    *   `find` must be a non-empty string.
*   **Postconditions:**
    *   On success, the file at `path` is updated with the `replace` string substituted for the first occurrence of the `find` string.
    *   If no file exists at `path`, a `FileNotFoundError` must be raised.
    *   If the `find` string is not found in the file, a custom `FindStringNotFoundError` must be raised. This exception should contain the full, unmodified content of the file to be used for reporting purposes.

## 3. Related Spikes

*   N/A
