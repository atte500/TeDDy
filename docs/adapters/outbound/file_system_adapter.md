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

## 4. Related Spikes

*   [/spikes/technical/02-exclusive-file-creation/](/spikes/technical/02-exclusive-file-creation/): This spike verified that using `open(path, 'x')` correctly raises a `FileExistsError` if the file already exists, confirming the proposed implementation strategy.

## 5. External Documentation

*   [Python `open()` function documentation](https://docs.python.org/3/library/functions.html#open)
