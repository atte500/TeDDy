# Outbound Port: `FileSystemManager`

**Status:** Implemented
**Introduced in:** [Slice 02: Implement `create_file` Action](../../slices/02-create-file-action.md)

## 1. Responsibility

The `FileSystemManager` port defines a technology-agnostic interface for interacting with a file system. It provides methods for common file operations like creating, reading, and updating files, abstracting the details away from the application's core logic.

## 2. Methods

### `create_file`
**Status:** Implemented

*   **Description:** Creates a new file at a specified path with the given content. The operation must be atomic. The parent directory is assumed to exist.
*   **Signature:** `create_file(path: str, content: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   No file must exist at the specified `path`.
*   **Postconditions:**
    *   On success, a new file is created at `path` containing the exact `content`.
    *   If a file already exists at `path`, a `FileAlreadyExistsError` must be raised. **(Updated in: [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md))**

---

### `read_file`
**Status:** Implemented

*   **Description:** Reads the entire content of a file at a specified path.
*   **Signature:** `read_file(path: str) -> str`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   A file must exist at the specified `path`.
*   **Postconditions:**
    *   On success, returns the full string content of the file.
    *   If no file exists at `path`, a `FileNotFoundError` (or a custom domain equivalent) must be raised.

---

### `write_file`
**Status:** Planned
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

*   **Description:** Writes content to a file at a specified path. If the file exists, it is overwritten. If it does not exist, it is created. This is an "upsert" operation.
*   **Signature:** `write_file(path: str, content: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
*   **Postconditions:**
    *   A file exists at `path` with the specified `content`.

---

### `edit_file`
**Status:** Implemented
**Introduced in:** [Slice 06: Implement `edit` Action](../../slices/06-edit-action.md)

*   **Description:** Finds and replaces the first occurrence of a specific string within a file.
*   **Signature:** `edit_file(path: str, find: str, replace: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   A file must exist at the specified `path`.
    *   `find` must be a non-empty string.
*   **Postconditions:**
    *   On success, the file at `path` is updated with the `replace` string substituted for the single occurrence of the `find` string.
    *   If no file exists at `path`, a `FileNotFoundError` must be raised.
    *   If the `find` string is not found in the file, a `SearchTextNotFoundError` must be raised. **(Updated in: [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md))**
    *   If the `find` string is found more than once in the file, a `MultipleMatchesFoundError` must be raised. **(Introduced in: [Slice 09: Enhance `edit` Action Safety](../../slices/09-enhance-edit-action-safety.md))**

---

### `path_exists`
**Status:** Planned
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

*   **Description:** Checks for the existence of a file or directory at the given path.
*   **Signature:** `path_exists(path: str) -> bool`
*   **Postconditions:**
    *   Returns `True` if a file or directory exists at `path`, otherwise `False`.

---

### `create_directory`
**Status:** Planned
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

*   **Description:** Creates a new directory. This operation should be idempotent (i.e., not fail if the directory already exists).
*   **Signature:** `create_directory(path: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid path for a directory.
*   **Postconditions:**
    *   A directory exists at the specified `path`.

## 3. Related Spikes

*   N/A
