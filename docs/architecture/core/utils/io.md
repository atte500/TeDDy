# Component Design: Tee
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/utils/io.py`](/src/teddy_executor/core/utils/io.py)

## Purpose
Provides a `Tee` context manager and a `_TeeWriter` stream proxy that duplicate `sys.stdout` and `sys.stderr` writes into a session log file. It lets `SessionOrchestrator` produce `history.log` from existing console output without adding new log statements.

## Consumers
- [`SessionOrchestrator`](../services/session_orchestrator.md): Wraps the session execution loop in a `Tee` context to write `history.log`.

## Dependencies
None — the module uses only the Python standard library (`sys`, `re`, `logging`).

## Class Invariants
- `stream_restoration`: `__exit__` restores the original `sys.stdout` and `sys.stderr` even when the body raises.
- `ansi_stripping`: The terminal receives raw text with colours intact; the log file receives the same text with ANSI escape sequences removed.
- `fail_soft_logging`: A closed or unwritable log file is detected once and then skipped; console output is never affected.
- `handler_symmetry`: `__enter__` replaces the root logging handlers, and `__exit__` removes the Tee handler by instance identity before restoring the saved handlers.

## Inbound Ports
None — this is a utility context manager, not a port-driven component.

## Outbound Ports
None — the module writes directly to the process streams and the log file.

## Data Contracts
- **`Tee`**: The context manager holding the optional log file, the saved streams, and the saved logging handlers.
- **`_TeeWriter`**: The stream proxy exposing `write`, `flush`, `isatty`, `fileno`, and `encoding`.

## Operations

### `Tee(log_file)`
- **Preconditions:** `log_file` is an open text stream, or `None` to disable tee-ing.
- **Postconditions:** Stores the log file for `__enter__`.

### `__enter__() -> Tee`
- **Postconditions:** Saves `sys.stdout` and `sys.stderr`, replaces them with `_TeeWriter` proxies when a log file is present, and installs a `logging.StreamHandler` bound to the proxied `sys.stderr`. Returns `self`.

### `__exit__(exc_type, exc_val, exc_tb) -> None`
- **Postconditions:** Removes the Tee logging handler, restores the saved root handlers, restores the original streams, and closes the log file.

### `_TeeWriter.write(text) -> None`
- **Postconditions:** Writes `text` to the original stream and the ANSI-stripped text to the log file, flushing both.

### `_TeeWriter.flush() -> None`
- **Postconditions:** Flushes both the original stream and the log file.

### `_TeeWriter.isatty() -> bool`
- **Postconditions:** Returns the original stream's TTY status.

### `_TeeWriter.fileno() -> int`
- **Postconditions:** Returns the original stream's file descriptor so descriptor-based terminal checks keep working.
