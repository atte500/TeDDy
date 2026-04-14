# Bug: Terminal State Corruption on Timeout

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

- **Observed Behavior:** When an `EXECUTE` action times out, the terminal is left in a "raw" state (e.g., no echo, broken line endings, cursor issues), requiring a `reset` or terminal restart.
- **Expected Behavior:** Terminal state should be restored even if an execution times out.

## System Model

### Understanding
- The TUI execution path (`orchestrate_execution` -> `_execute_silently` -> `ActionDispatcher` -> `ShellAdapter`) triggers `subprocess.run` for `EXECUTE` actions.
- Textual keeps the terminal in "raw mode" for its UI. `subprocess.run` also attempts to manage TTY state for the child process.
- `orchestrate_execution` is missing a `with app.suspend():` context manager, which is required whenever the TUI needs to yield terminal control to an external process.
- When `EXECUTE` runs without suspension, the terminal state becomes inconsistent. On timeout, the child process is killed, potentially leaving the terminal in a "fucked up" state because Textual's own state restoration logic was never cleanly bypassed and resumed.

### Discrepancies
- None.

## Solution

### Implemented Fixes
- Wrapped the execution logic in `orchestrate_execution` (located in `textual_plan_reviewer_helpers.py`) with `with app.suspend():`.
- This ensures that the Textual TUI yields terminal control whenever an action is executed, preventing conflicts with `subprocess.run` inside `ShellAdapter`.

### Prevention
- A regression test should be added to ensure that any execution from a TUI context always uses the suspension pattern.
- Developers should favor using the `app.suspend()` context manager for any synchronous operation that might involve terminal I/O or subprocesses.
