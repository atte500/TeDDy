# Outbound Adapter: `LocalFileSystemAdapter`

**Status:** Implemented
**Introduced in:**
- [Slice 02: Implement `create_file` Action](../../slices/executor/02-create-file-action.md)
- [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)

## 1. Responsibility

The `LocalFileSystemAdapter` implements the `FileSystemManager` port to provide concrete file system operations on the local machine where the `teddy` executor is running.

## 2. Implemented Ports

*   [FileSystemManager](../../core/ports/outbound/file_system_manager.md)

## 3. Implementation Notes

The adapter will leverage Python's built-in `pathlib` and `open()` functions for file operations.

*   **File Creation (`create_file`):** To satisfy the port's requirement for exclusive creation (failing if a file already exists), the `create_file` method will use the `'x'` (exclusive creation) mode when calling `open()`.
*   **Error Handling (`create_file`):** (**Updated in:** [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md)) If `open()` is called with `'x'` mode on a path that already exists, it will raise a standard `FileExistsError`. The adapter must catch this and re-raise it as the domain-specific `FileAlreadyExistsError`, attaching the file path to the exception, to fulfill the port's contract.
*   **File Reading (`read_file`):** (**Introduced in:** [Slice 04: Implement `read_file` Action](../../slices/04-read-action.md)) The `read_file` method will use the standard `'r'` (read) mode with `utf-8` encoding. It must catch `FileNotFoundError` if the path does not exist and `UnicodeDecodeError` for non-text files, propagating these as failures.
*   **File Writing (`write_file`):** (**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)) The `write_file` method will use Python's `pathlib.Path.write_text()`. This conveniently handles both creating a new file and overwriting an existing one, fulfilling the "upsert" requirement of the port.
*   **File Editing (`edit_file`):** (**Updated in:** [Slice 09: Enhance `edit` Action Safety](../../slices/09-enhance-edit-action-safety.md)) The `edit_file` method first reads the file's content. It then counts the number of occurrences of the `find` string.
    *   If the count is 0, it raises `SearchTextNotFoundError`.
    *   If the count is greater than 1, it raises `MultipleMatchesFoundError`.
    *   If the count is exactly 1, it performs the replacement and writes the new content back to the file.
*   **Path Existence (`path_exists`):** (**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)) This will be implemented using `pathlib.Path.exists()`, which correctly checks for both files and directories.
*   **Directory Creation (`create_directory`):** (**Introduced in:** [Slice 13: Implement `context` Command](../../slices/executor/13-context-command.md)) This will use `pathlib.Path.mkdir()` with the `parents=True` and `exist_ok=True` flags. This ensures the method is idempotent and can create parent directories as needed.
*   **Default Context File Creation (`create_default_context_file`):** (**Introduced in:** [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)) This method creates the `.teddy` directory if it doesn't exist, adds a `.gitignore` file inside it to ignore all contents, and creates a default `perm.context` file with a simple list of starting files (`README.md`, `docs/ARCHITECTURE.md`).
*   **Context Path Gathering (`get_context_paths`):** (**Introduced in:** [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)) This method finds all files ending with `.context` inside the `.teddy` directory, reads them, and returns a sorted, deduplicated list of all file paths, ignoring comments and empty lines.
*   **Vault File Reading (`read_files_in_vault`):** (**Introduced in:** [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)) This method takes a list of file paths and returns a dictionary mapping each path to its content. If a file is not found, the path is still included in the dictionary, but its value is `None`.

## 4. Key Code Snippets

### `create_file`
**(Updated in: [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md))**
```python
# Note: FileAlreadyExistsError is a custom exception from the domain model
from teddy.core.domain import FileAlreadyExistsError

def create_file(self, path: str, content: str) -> None:
    try:
        with open(path, "x", encoding="utf-8") as f:
            f.write(content)
    except FileExistsError:
        # Catch the standard Python error and raise the specific domain exception
        raise FileAlreadyExistsError(file_path=path)
    except IOError as e:
        # Propagate other IO errors
        raise IOError(f"Failed to create file at {path}: {e}") from e
```

### `read_file`
**Introduced in:** [Slice 04: Implement `read_file` Action](../../slices/04-read-action.md)
```python
def read_file(self, path: str) -> str:
    """
    Reads the content of a file from the specified path.
    """
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        # Re-raise to conform to the port's contract
        raise
    except IOError as e:
        raise IOError(f"Failed to read file at {path}: {e}") from e
```

### `write_file`
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)
```python
from pathlib import Path

def write_file(self, path: str, content: str) -> None:
    try:
        Path(path).write_text(content, encoding="utf-8")
    except IOError as e:
        raise IOError(f"Failed to write to file at {path}: {e}") from e
```

### `edit_file`
**(Updated in: [Slice 09: Enhance `edit` Action Safety](../../slices/09-enhance-edit-action-safety.md))**
```python
# Note: Exceptions are from the domain model
from teddy.core.domain.models import SearchTextNotFoundError, MultipleMatchesFoundError

def edit_file(self, path: str, find: str, replace: str) -> None:
    # This is a conceptual example. The actual implementation handles multiline cases.
    original_content = Path(path).read_text(encoding="utf-8")

    # 1. Count occurrences to check for ambiguity.
    num_matches = original_content.count(find)

    # 2. Raise domain-specific exceptions based on the count.
    if num_matches > 1:
        raise MultipleMatchesFoundError(
            message=f"Found {num_matches} occurrences. Aborting.",
            content=original_content,
        )
    if num_matches == 0:
        raise SearchTextNotFoundError(
            message="Search text was not found.",
            content=original_content,
        )

    # 3. Perform the replacement, now guaranteed to be a single, unambiguous match.
    new_content = original_content.replace(find, replace, 1)
    Path(path).write_text(new_content, encoding="utf-8")
```

### `path_exists`
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)
```python
from pathlib import Path

def path_exists(self, path: str) -> bool:
    return Path(path).exists()
```

### `create_directory`
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)
```python
from pathlib import Path

def create_directory(self, path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)
```

### `create_default_context_file`
**Introduced in:** [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)
```python
def create_default_context_file(self) -> None:
    teddy_dir = self.root_dir / ".teddy"
    teddy_dir.mkdir(exist_ok=True)

    gitignore_file = teddy_dir / ".gitignore"
    gitignore_file.write_text("*", encoding="utf-8")

    perm_context_file = teddy_dir / "perm.context"
    default_content = "README.md\ndocs/ARCHITECTURE.md\n"
    perm_context_file.write_text(default_content, encoding="utf-8")
```

### `get_context_paths`
**Introduced in:** [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)
```python
def get_context_paths(self) -> list[str]:
    teddy_dir = self.root_dir / ".teddy"
    if not teddy_dir.is_dir():
        return []

    all_paths = set()
    context_files = list(teddy_dir.glob("*.context"))

    for context_file in context_files:
        content = context_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped_line = line.strip()
            if stripped_line and not stripped_line.startswith("#"):
                all_paths.add(stripped_line)

    return sorted(list(all_paths))
```

### `read_files_in_vault`
**Introduced in:** [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)
```python
def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
    contents: dict[str, str | None] = {}
    for path in paths:
        try:
            full_path = self.root_dir / path
            contents[path] = self.read_file(str(full_path))
        except FileNotFoundError:
            contents[path] = None
    return contents
```


## 5. Related Spikes

*   [/spikes/technical/02-exclusive-file-creation/](/spikes/technical/02-exclusive-file-creation/): This spike verified that using `open(path, 'x')` correctly raises a `FileExistsError` if the file already exists, confirming the proposed implementation strategy.

## 6. External Documentation

*   [Python `open()` function documentation](https://docs.python.org/3/library/functions.html#open)
*   [Python `pathlib` module documentation](https://docs.python.org/3/library/pathlib.html)
