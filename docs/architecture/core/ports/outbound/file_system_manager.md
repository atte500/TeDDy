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
**Status:** Implemented
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

*   **Description:** Modifies an existing file by applying a list of find-and-replace blocks. **(Updated in: [Slice 09-02: Auto-Initialization](../../slices/09-02-auto-initialization.md))**
*   **Signature:** `edit_file(path: str, edits: list[dict[str, str]]) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   A file must exist at the specified `path`.
*   **Postconditions:**
    *   On success, the file at `path` is updated with the `replace` string substituted for the single occurrence of each `find` string.
    *   If no file exists at `path`, a `FileNotFoundError` must be raised.
    *   If any `find` string is not found in the file, a `SearchTextNotFoundError` must be raised.
    *   If any `find` string is found more than once in the file, a `MultipleMatchesFoundError` must be raised.

---

### `path_exists`
**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

*   **Description:** Checks for the existence of a file or directory at the given path.
*   **Signature:** `path_exists(path: str) -> bool`
*   **Postconditions:**
    *   Returns `True` if a file or directory exists at `path`, otherwise `False`.

---

### `create_directory`
**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

*   **Description:** Creates a new directory. This operation should be idempotent (i.e., not fail if the directory already exists).
*   **Signature:** `create_directory(path: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid path for a directory.
*   **Postconditions:**
    *   A directory exists at the specified `path`.

---

### `get_mtime`
**Status:** Implemented
**Introduced in:** [Slice 09-07: UX Polish & Logging](../../slices/09-07-ux-polish-logging.md)

*   **Description:** Returns the modification time of a file or directory as a timestamp.
*   **Signature:** `get_mtime(path: str) -> float`
*   **Preconditions:**
    *   `path` must exist.
*   **Postconditions:**
    *   Returns the `st_mtime` from the file system.

---

### `resolve_paths_from_files`
**Status:** Planned
**Introduced in:** [Slice 09-04](../../slices/09-04-core-session-context-engine.md)

*   **Description:** Reads a list of `.context` files and returns a deduplicated list of the paths they contain.
*   **Signature:** `resolve_paths_from_files(file_paths: Sequence[str]) -> List[str]`
*   **Preconditions:**
    -   Each path in `file_paths` must exist.
*   **Postconditions:**
    -   Returns a sorted, unique list of all non-commented file paths found within the specified context files.
