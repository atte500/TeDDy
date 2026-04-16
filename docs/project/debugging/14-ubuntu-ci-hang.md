# Bug: Ubuntu CI Test Suite Hang

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- Pytest suite hangs on Ubuntu CI workers.
- Windows and macOS CI workers pass.
- Hang occurs at ~24% progress (approx. 140-150 tests in).
- CI job times out after 45 minutes.
- **MRE:** `[Pending]`

## Diagnostic Analysis

### Causal Model
- **Test Execution:** `pytest` is run with `-n auto` (xdist) and `pytest-timeout`.
- **Environment:** Ubuntu uses `fork` as the default multiprocessing start method.
- **Recent Changes:** Fixes to `ExecutionOrchestrator` and `ReviewerApp` involving TUI suspension and manual execution logic.
- **Potential Conflict:** A test might be triggering a TUI `app.suspend()` or a background thread that deadlocks during a `fork` or fails to release a lock/resource on Linux.

### Discrepancies
- Suite hangs on Linux but passes on macOS/Windows.
- `pytest-timeout` (signal method) fails to terminate the hanging test or worker. (resolved: If the hang happens in a recursive call that exhausts the stack or hits a syscall in a loop, signal-based timeouts can sometimes be delayed or blocked if xdist forking is involved).
- `LocalRepoTreeGenerator` does not handle circular symlinks. (resolved: Confirmed infinite recursion in `_walk` when encountering symlinks to parent directories).

### Investigation History
- [2026-04-16] Initial report. Observed CI log showing hang at 24% with 4 workers.
- [2026-04-16] Identified `LocalRepoTreeGenerator` as the cause of the hang during Test 144. Confirmed infinite recursion in `_walk` when encountering circular symlinks.
- [2026-04-16] Applied fix to skip symlinks during tree traversal and formatting. Verified with MRE and regression test.

## Solution
### Implemented Fixes
- **LocalRepoTreeGenerator:** Modified `_walk` and `_format_recursive` to explicitly check for symlinks using `path.is_symlink()`.
- **Symlink Protection:** Real directories are now distinguished from symlinks. Symlinks are treated as files in the tree representation, preventing the generator from following them and entering infinite loops.

### Prevention
- **Regression Test:** Added `test_tree_generator_handles_circular_symlinks_without_hanging` to the integration suite. This test creates a circular symlink and verifies that `generate_tree()` completes successfully without recursion.