# Outbound Adapter: `LocalFileSystemAdapter`

**Introduced in:** [Slice 02: Implement `create_file` Action](../../slices/02-create-file-action.md)

## 1. Responsibility

The `LocalFileSystemAdapter` implements the `FileSystemManager` port to provide concrete file system operations on the local machine where the `teddy` executor is running.

## 2. Implemented Ports

*   [FileSystemManager](../../core/ports/outbound/file_system_manager.md)

## 3. Implementation Notes

The adapter will leverage Python's built-in `open()` function for file operations.

*   **File Creation:** To satisfy the port's requirement for exclusive creation (failing if a file already exists), the `create_file` method will use the `'x'` (exclusive creation) mode when calling `open()`.
*   **Error Handling:** If `open()` is called with `'x'` mode on a path that already exists, it will raise a `FileExistsError`. The adapter must catch this specific exception and propagate it as a failure, fulfilling the port's contract. Other `IOError` exceptions (like permission errors) should also be handled gracefully.
*   **File Reading:** (**Introduced in:** [Slice 04: Implement `read_file` Action](../../slices/04-read-action.md)) The `read_file` method will use the standard `'r'` (read) mode with `utf-8` encoding. It must catch `FileNotFoundError` if the path does not exist and `UnicodeDecodeError` for non-text files, propagating these as failures.

## 4. Key Code Snippets

### `create_file`

```python
def create_file(self, path: str, content: str) -> Result[None, str]:
    try:
        with open(path, "x", encoding="utf-8") as f:
            f.write(content)
        return Ok(None)
    except FileExistsError:
        return Err(f"File already exists at path: {path}")
    except IOError as e:
        return Err(f"Failed to create file at {path}: {e}")

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

## 5. Related Spikes

*   [/spikes/technical/02-exclusive-file-creation/](/spikes/technical/02-exclusive-file-creation/): This spike verified that using `open(path, 'x')` correctly raises a `FileExistsError` if the file already exists, confirming the proposed implementation strategy.

## 6. External Documentation

*   [Python `open()` function documentation](https://docs.python.org/3/library/functions.html#open)
