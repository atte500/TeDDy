# Component Design: I/O Utilities (Tee)

- **Status:** Implemented

## Purpose / Responsibility
Provide a `Tee` context manager that duplicates output writes from `sys.stdout` and `sys.stderr` to a log file. Used by `SessionOrchestrator` to produce the session `history.log` by capturing existing console output without adding new log statements.

## Failure Modes
- **File open failure**: If the log file cannot be opened (permissions, disk full), the Tee logs a debug warning and silently skips tee'ing. The session continues without a history.log.
- **Write failure**: If writing to the log file fails mid-turn, the exception propagates. Console output is unaffected (the proxy writer writes to the original stream first).
- **Restore failure**: If `__exit__` cannot restore `sys.stdout`/`sys.stderr`, the process is corrupted. This is prevented by saving the original references before replacement and restoring in `finally` block.
- **Flush failure**: If flushing the log file fails, the error is swallowed (logged) to prevent crashing the session.

## Ports
- **Inbound**: None (utility class, not a Port-driven component).
- **Outbound**: None. The Tee directly interacts with Python's `sys.stdout`, `sys.stderr`, and file I/O.
- **Consumed by**: `SessionOrchestrator.execute()`.

## Implementation Details / Logic
The Tee is a context manager that:
1. Saves references to the original `sys.stdout` and `sys.stderr`.
2. Opens the `history.log` file in append mode (`"a"`, UTF-8 encoding).
3. Creates two `_TeeWriter` instances: one for stdout (writes to original stdout + log file), one for stderr (writes to original stderr + log file).
4. Replaces `sys.stdout` and `sys.stderr` with these writers.
5. On `__exit__`, restores the original streams and closes the log file.

The `_TeeWriter` class:
- `write(text)`: Calls `original.write(text)` followed by `log_file.write(text)`, flushing both.
- `flush()`: Flushes both original and log file.
- `isatty()`: Delegates to the original stream.

## Data Contracts / Methods

### `Tee.__init__(log_path: Path)`
- **Args**: `log_path` — Filesystem path for the history.log file.
- **Pre-conditions**: Parent directory exists.
- **Post-conditions**: Stores log_path for `__enter__`.

### `Tee.__enter__() -> Tee`
- **Actions**:
  1. Save `sys.stdout` and `sys.stderr` as `_original_stdout`, `_original_stderr`.
  2. Open `log_path` for append (UTF-8). If `OSError`, log debug warning, return self (no tee).
  3. Create `_TeeWriter(original_stdout, log_file)` → install as `sys.stdout`.
  4. Create `_TeeWriter(original_stderr, log_file)` → install as `sys.stderr`.
- **Returns**: self.

### `Tee.__exit__(exc_type, exc_val, exc_tb) -> None`
- **Actions**:
  1. Restore `sys.stdout` to `_original_stdout`.
  2. Restore `sys.stderr` to `_original_stderr`.
  3. Close `_log_file` (swallow `OSError` with debug log).

### `_TeeWriter.__init__(original: TextIO, log_file: TextIO)`
- **Args**: `original` — the real stdout/stderr stream; `log_file` — the shared log file stream.

### `_TeeWriter.write(text: str) -> None`
- Writes `text` to both `original` and `log_file`, flushing both immediately.

### `_TeeWriter.flush() -> None`
- Flushes both `original` and `log_file`.

### `_TeeWriter.isatty() -> bool`
- Returns `original.isatty()`.
