# Component Design: FileSystemObserver
- **Status:** Implemented
- **Source:** [`tests/harness/observers/file_system_observer.py`](/tests/harness/observers/file_system_observer.py)

## Purpose
A test-harness observer that performs assertions against the local file system. It turns low-level `pathlib` checks into a small, expressive assertion API for verifying the side effects of file operations.

## Consumers
- Integration and acceptance test suites: Verify file and directory side effects after a command runs.

## Dependencies
None — the observer uses only the Python standard library.

## Class Invariants
- `read_only`: Every method inspects the file system and never mutates it.
- `fail_loud`: A failed assertion raises `AssertionError` carrying the expected and actual values.

## Inbound Ports
None — this is a test harness component.

## Outbound Ports
None — this is a test harness component.

## Data Contracts
- **Assertion inputs:** `pathlib.Path` targets and expected content values.

## Operations

### `assert_file_exists(path) -> None`
- **Postconditions:** Returns when the file exists; otherwise raises `AssertionError`.

### `assert_file_content_equals(path, expected) -> None`
- **Postconditions:** Returns when the file content equals `expected`; otherwise raises `AssertionError` with both values.

### `assert_directory_contains(root, expected_files) -> None`
- **Postconditions:** Returns when the sorted set of relative file paths under `root` equals the sorted `expected_files`; otherwise raises `AssertionError`.

### `assert_file_matches_pattern(path, pattern) -> None`
- **Postconditions:** Returns when the file content matches the regular expression `pattern`; otherwise raises `AssertionError`.
