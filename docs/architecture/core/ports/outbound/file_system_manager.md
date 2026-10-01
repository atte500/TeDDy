# Outbound Port: `FileSystemManager`

**Status:** Implemented

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
    *   If a file already exists at `path`, a `FileAlreadyExistsError` must be raised.

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

*   **Description:** Writes content to a file at a specified path. If the file exists, it is overwritten. If it does not exist, it is created. This is an "upsert" operation.
*   **Signature:** `write_file(path: str, content: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
*   **Postconditions:**
    *   A file exists at `path` with the specified `content`.

---

### `edit_file`
**Status:** Implemented

*   **Description:** Modifies an existing file by applying a list of find-and-replace blocks.
*   **Signature:** `edit_file(path: str, edits: list[dict[str, str]], similarity_threshold: float = 0.8) -> None`
*   **Preconditions:**
    *   `path` must be a valid, non-empty string representing a file path.
    *   A file must exist at the specified `path`.
    *   `similarity_threshold` must be a float between 0.0 and 1.0.
*   **Postconditions:**
    *   On success, the file at `path` is updated with the `replace` string substituted for the best-matching occurrence of each `find` string.
    *   If no file exists at `path`, a `FileNotFoundError` must be raised.
    *   If no match for a `find` string meets the `similarity_threshold`, a `SearchTextNotFoundError` must be raised.
    *   If multiple matches for a `find` string share the same highest similarity score (ambiguity), a `MultipleMatchesFoundError` must be raised.
---

### `path_exists`
**Status:** Implemented

*   **Description:** Checks for the existence of a file or directory at the given path.
*   **Signature:** `path_exists(path: str) -> bool`
*   **Postconditions:**
    *   Returns `True` if a file or directory exists at `path`, otherwise `False`.

---

### `is_dir`
**Status:** Implemented

*   **Description:** Checks if the specified path is a directory.
*   **Signature:** `is_dir(path: str) -> bool`
*   **Postconditions:**
    *   Returns `True` if the path exists and is a directory.

---

### `list_directory_recursive`
**Status:** Implemented

*   **Description:** Lists all files within a directory recursively, respecting ignore rules.
*   **Signature:** `list_directory_recursive(path: str) -> list[str]`
*   **Preconditions:**
    *   `path` must exist and be a directory.
*   **Postconditions:**
    *   Returns a list of root-relative file paths.

---

### `create_directory`
**Status:** Implemented

*   **Description:** Creates a new directory. This operation should be idempotent (i.e., not fail if the directory already exists).
*   **Signature:** `create_directory(path: str) -> None`
*   **Preconditions:**
    *   `path` must be a valid path for a directory.
*   **Postconditions:**
    *   A directory exists at the specified `path`.

---

### `create_directory_exclusive`
**Status:** Implemented

*   **Description:** Atomically creates a directory (including any necessary parent directories) and fails if it already exists. The existence check and creation are a single atomic OS operation (no check-then-act window), making this safe for concurrent processes racing to claim the same path on both POSIX and Windows — exactly one caller wins.
*   **Signature:** `create_directory_exclusive(path: str) -> bool`
*   **Preconditions:**
    *   `path` must be a valid path for a directory.
*   **Postconditions:**
    *   Returns `True` if the directory was created by this call.
    *   Returns `False` if the directory already existed (`FileExistsError` caught).
    *   Any error other than `FileExistsError` (e.g., permission denied) is re-raised (Failure Transparency).
*   **Intended Use:** Claiming session roots (`.teddy/sessions/{timestamp}-{name}`) so concurrent session creation and turn-100 migration can never silently overwrite an existing session's audit ledger.

---

### `get_mtime`
**Status:** Implemented

*   **Description:** Returns the modification time of a file or directory as a timestamp.
*   **Signature:** `get_mtime(path: str) -> float`
*   **Preconditions:**
    *   `path` must exist.
*   **Postconditions:**
    *   Returns the `st_mtime` from the file system.

---

### `resolve_paths_from_files`
**Status:** Planned

*   **Description:** Reads a list of `.context` files and returns a deduplicated list of the paths they contain.
*   **Signature:** `resolve_paths_from_files(file_paths: Sequence[str]) -> List[str]`
*   **Preconditions:**
    -   Each path in `file_paths` must exist.
*   **Postconditions:**
    -   Returns a sorted, unique list of all non-commented file paths found within the specified context files.
