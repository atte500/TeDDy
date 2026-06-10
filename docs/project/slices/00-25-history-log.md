# Slice: Session History Log (history.log)
- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md)
- **Prototype:** [docs/project/tasks/25-history-log-implementation.md](/docs/project/tasks/25-history-log-implementation.md)
- **Component Docs:** [docs/architecture/core/services/session_orchestrator.md](/docs/architecture/core/services/session_orchestrator.md), [docs/architecture/core/utils/io.md](/docs/architecture/core/utils/io.md) (new)

## Business Goal
Provide a persistent, chronological log of all turn activity in a session for easy auditing, review, and debugging. Users can open `history.log` to see exactly what happened in each turn without navigating individual turn directories. The log is a pure capture of existing console output — no new log lines are added.

## Scenarios

> As a user, I want a single log file that captures all console output from my session turns so that I can review what happened without navigating individual turn directories.

```gherkin
Given a session with at least one completed turn
When the first turn executes
Then a file named history.log exists in the session root directory
And it contains the console output that was printed during that turn (both stdout and stderr)
```

> As a user, I want the log to be appended across multiple turns so that the full session history is available in one file.

```gherkin
Given a session with two completed turns
When both turns have executed
Then the history.log contains both turns' output in chronological order
And the second turn's content is appended after the first
```

> As a user, I want the log to be generated only in session mode so that standalone execute calls do not create a history.log.

```gherkin
Given a standalone execute call (non-session)
When the plan executes
Then no history.log is created in the session directory
```

> As a user, I want both stdout and stderr to be captured so that the log includes all output, not just the stdout stream.

```gherkin
Given a session turn that prints to stderr (e.g., error messages, action statuses)
When the turn executes
Then the history.log contains those stderr lines interleaved with stdout lines
```

## Edge Cases
- **File open failure**: If the log file cannot be opened (permissions), the session continues without a history.log. A debug warning is logged.
- **Write failure**: If writing to the log file fails mid-turn, the exception propagates. Console output is unaffected.
- **Validation failure turn**: The log captures any console output that was printed before/during the validation failure (e.g., error messages to stderr).
- **Communication turn (MESSAGE)**: The log captures whatever output is printed (typically only turn transition messages).
- **Non-session mode**: Tee is not installed; no history.log is created.
- **Session branching**: If a session directory is copied, the history.log is copied with it. Each branch has its own log continuing from the branch point.
- **Unicode characters**: File opened with UTF-8 encoding.
- **Flush on each write**: Ensures no data loss on crash.
- **Stdout/stderr restoration**: After Tee exits, sys.stdout and sys.stderr are restored to originals. Exception safety ensures this always happens.

## Deliverables
- [x] **Contract** - Define Tee class interface (takes Path, context manager, proxies write/flush/isatty to both original stdout/stderr and log file).
- [x] **Logic** - Implement Tee class in `src/teddy_executor/core/utils/io.py` (dual capture of stdout and stderr).
- [x] **Wiring** - Install Tee at start of SessionOrchestrator.execute() when is_session is True, with try/finally for cleanup of both streams.
- [▶] **Harness** - Create test fixtures and helpers for Tee and history.log tests.
- [ ] **Wiring** - Add unit tests for Tee class (basic tee both streams, flush propagation, isatty forwarding, context manager restore, exception safety for file open failure).
- [ ] **Wiring** - Add integration tests for history.log creation in SessionOrchestrator (stdout + stderr capture, validation failure logging, non-session mode, append mode, stream restoration on exception, Tee failure isolation).

## Implementation Notes
*(To be filled during implementation)*

## Implementation Plan
The implementation follows the updated design:
1. Create the `Tee` context manager class in `src/teddy_executor/core/utils/io.py` that replaces both `sys.stdout` and `sys.stderr` with proxy writers.
2. Modify `SessionOrchestrator.execute()` to install the Tee at the start when `is_session` is True, with `try/finally` for cleanup.
3. Do NOT add any new `typer.echo()` calls for a metadata header — the log is a pure capture of existing output.
4. Handle edge cases (file open failure, write failure, non-session mode).
5. Add unit tests for Tee and integration tests for SessionOrchestrator.

The Tee is a context manager that:
- Accepts a `Path` to the log file.
- Saves references to original `sys.stdout` and `sys.stderr`.
- Opens the log file in append mode ("a", UTF-8 encoding).
- Creates two `_TeeWriter` instances (stdout proxy, stderr proxy).
- Installs them in place of the original streams.
- On `__exit__`, restores originals and closes the log file.

Key method: `SessionOrchestrator.execute()` installs Tee after determining `is_session` (after line ~30), wraps the rest of the method in try/finally.

Test strategy:
- Tee unit tests: Verify write propagation for both stdout and stderr, flush, isatty, context manager restore, exception safety.
- SessionOrchestrator tests: Use test doubles to simulate session turn execution and verify history.log creation and content for both streams.
- Integration: Run orchestration with mocked dependencies and assert file existence and content.
