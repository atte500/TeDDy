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
*   **File Editing:** (**Updated in:** [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md)) The `edit_file` method will follow a read-modify-write pattern. It will first read the entire file into memory. If the `find` string is not present in the content, it must raise the domain-specific `TextBlockNotFoundError`, attaching the file path to the exception, per the port's contract. If the string is found, it will perform the replacement and then open the same file in `'w'` (write) mode to overwrite it with the new content.

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
**(Updated in: [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md))**
```python
# Note: TextBlockNotFoundError is a custom exception from the domain model
from teddy.core.domain import TextBlockNotFoundError

def edit_file(self, path: str, find: str, replace: str) -> None:
    try:
        # 1. Read
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # 2. Modify
        if find not in content:
            # Raise the specific domain exception with the file path
            raise TextBlockNotFoundError(file_path=path)

        new_content = content.replace(find, replace, 1) # Replace only the first occurrence

        # 3. Write
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

    except FileNotFoundError:
        # Re-raise to be handled by the service layer
        raise
    except IOError as e:
        # Re-raise a more generic error for other IO problems
        raise IOError(f"Failed to edit file at {path}: {e}") from e
```

## 5. Related Spikes

*   [/spikes/technical/02-exclusive-file-creation/](/spikes/technical/02-exclusive-file-creation/): This spike verified that using `open(path, 'x')` correctly raises a `FileExistsError` if the file already exists, confirming the proposed implementation strategy.

## 6. External Documentation

*   [Python `open()` function documentation](https://docs.python.org/3/library/functions.html#open)
