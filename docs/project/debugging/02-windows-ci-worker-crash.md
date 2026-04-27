# Case File: 02-windows-ci-worker-crash
- **Agent:** Debugger
- **Status:** Unresolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
The Windows CI pipeline is experiencing widespread test failures where `pytest-xdist` workers (`gw0`, `gw1`, etc.) crash with the message `node down: Not properly terminated`. These crashes occur across multiple test suites, but only on the Windows platform. macOS and Linux jobs are passing.

### Expected Behavior
Tests should execute to completion and report standard pass/fail results without worker crashes.

### Actual Behavior
Multiple workers crash during test execution, leading to `FAILED` status for the affected tests with `worker 'gwX' crashed while running '...'`.

## Context & Scope
### Regressing Delta
The failure appears in the run titled "feat(cli): resequence session initialization to prompt before disk cr…". This PR likely introduced blocking I/O or state management that Windows handles differently than Unix-like systems.

### Environmental Triggers
- **OS:** Windows (win32)
- **Concurrency:** `pytest-xdist` (4 workers)
- **Runtime:** Python 3.11.9

### Ruled Out
- **macOS/Linux:** Definitive success in these environments suggests a platform-specific issue.

## Diagnostic Analysis
### Causal Model
1. The `teddy` CLI uses `typer.prompt` and `sys.stdin.read` for interactive turns.
2. Acceptance tests using `.with_real_interactor()` force the `ConsoleInteractor` to bypass mocks and perform real I/O.
3. On Windows, `pytest-xdist` workers running in parallel crash with `node down: Not properly terminated` when multiple processes attempt to grab or modify terminal state/stdin, especially if `termios` logic (Unix-only) is incorrectly triggered or if `stdin` is not a real TTY.
4. The crash is a terminal-contention issue exacerbated by parallel test execution on Windows.

### Discrepancies
- None yet recorded.

### Investigation History
- **Initial Observation:** Identified `node down: Not properly terminated` in Windows CI logs.

## Solution
### Implemented Fixes
- TBD

### Prevention
- TBD
