# Outbound Adapter: `LocalFileSystemAdapter`

**Introduced in:** [Slice 02: Implement `create_file` Action](../../slices/02-create-file-action.md)

## 1. Responsibility

The `LocalFileSystemAdapter` implements the `FileSystemManager` port to provide concrete file system operations on the local machine where the `teddy` executor is running.

## 2. Implemented Ports

*   [FileSystemManager](../../core/ports/outbound/file_system_manager.md)

## 3. Implementation Notes

The adapter will leverage Python's built-in `open()` function for file operations.

*   **File Creation:** To satisfy the port's requirement for exclusive creation (failing if a file already exists), the `create_file` method will use the `'x'` (exclusive creation) mode when calling `open()`.
*   **Error Handling:** (**Updated in:** [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md)) If `open()` is called with `'x'` mode on a path that already exists, it will raise a standard `FileExistsError`. The adapter must catch this and re-raise it as the domain-specific `FileAlreadyExistsError`, attaching the file path to the exception, to fulfill the port's contract.
*   **File Reading:** (**Introduced in:** [Slice 04: Implement `read_file` Action](../../slices/04-read-action.md)) The `read_file` method will use the standard `'r'` (read) mode with `utf-8` encoding. It must catch `FileNotFoundError` if the path does not exist and `UnicodeDecodeError` for non-text files, propagating these as failures.
*   **File Editing:** (**Updated in:** [Slice 09: Enhance `edit` Action Safety](../../slices/09-enhance-edit-action-safety.md)) The `edit_file` method first reads the file's content. It then counts the number of occurrences of the `find` string.
    *   If the count is 0, it raises `SearchTextNotFoundError`.
    *   If the count is greater than 1, it raises `MultipleMatchesFoundError`.
    *   If the count is exactly 1, it performs the replacement and writes the new content back to the file.
    This logic applies to both single-line and multiline `find` strings.

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
def read_file(self, path: str) -> Result[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return Ok(content)
    except FileNotFoundError:
        return Err(f"File not found at path: {path}")
    except UnicodeDecodeError:
        return Err(f"File at {path} is not a valid UTF-8 text file.")
    except IOError as e:
        return Err(f"Failed to read file at {path}: {e}")
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

## 5. Related Spikes

*   [/spikes/technical/02-exclusive-file-creation/](/spikes/technical/02-exclusive-file-creation/): This spike verified that using `open(path, 'x')` correctly raises a `FileExistsError` if the file already exists, confirming the proposed implementation strategy.

## 6. External Documentation

*   [Python `open()` function documentation](https://docs.python.org/3/library/functions.html#open)
