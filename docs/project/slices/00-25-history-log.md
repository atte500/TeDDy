# Slice: Session History Log (history.log)
- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/session-history-view.md](/docs/project/specs/session-history-view.md)
- **Prototype:** [docs/project/tasks/25-history-log-implementation.md](/docs/project/tasks/25-history-log-implementation.md)
- **Component Docs:** [docs/architecture/core/services/session_orchestrator.md](/docs/architecture/core/services/session_orchestrator.md), [docs/architecture/core/utils/io.md](/docs/architecture/core/utils/io.md) (new)

## Business Goal
Provide a persistent, chronological log of all turn activity in a session for easy auditing, review, and debugging. Users can open `history.log` to see exactly what happened in each turn without navigating individual turn directories.

## Scenarios

> As a user, I want a persistent chronological log of all turn activity in my session so that I can easily audit what happened without navigating individual turn directories.

```gherkin
Given a session with at least one completed turn
When the first turn executes
Then a file named history.log exists in the session root directory
And it contains the metadata header for the turn
And it contains action log entries with statuses
```

> As a user, I want the log to be appended across multiple turns so that the full session history is available in one file.

```gherkin
Given a session with two completed turns
When both turns have executed
Then the history.log contains both turns' content in chronological order
And the second turn's content is appended after the first
```

> As a user, I want the log to be generated only in session mode so that standalone execute calls do not create a history.log.

```gherkin
Given a standalone execute call (non-session)
When the plan executes
Then no history.log is created in the session directory
```

## Edge Cases
- **File open failure**: If the log file cannot be opened (permissions), the session continues without a history.log. A debug warning is logged.
- **Validation failure turn**: The log captures the header and validation error output before the failure.
- **Communication turn (MESSAGE)**: The log shows the header and metadata block only, followed by `MESSAGE - <content>` and `SUCCESS`.
- **Non-session mode**: Tee is not installed; no history.log is created.
- **Session branching**: If a session directory is copied, the history.log is copied with it. Each branch has its own log continuing from the branch point.
- **Unicode characters**: File opened with UTF-8 encoding.
- **Flush on each write**: Ensures no data loss on crash.
- **Stdout restoration**: After Tee exits, sys.stdout is restored to original. Exception safety ensures this always happens.

## Deliverables
- [ ] **Contract** - Define Tee class interface (takes Path, context manager, proxies write/flush/isatty to both stdout and log file).
- [ ] **Logic** - Implement Tee class in `src/teddy_executor/core/utils/io.py`.
- [ ] **Logic** - Add metadata header printing to stdout in SessionOrchestrator (required format: `[NN] <plan-title> | Waiting for <agent-name> to respond...`, plus model/context/cost bullets).
- [ ] **Wiring** - Install Tee at start of SessionOrchestrator.execute() when is_session is True, with try/finally for cleanup.
- [ ] **Harness** - Create test fixtures and helpers for Tee and history.log tests.
- [ ] **Wiring** - Add unit tests for Tee class (basic tee, flush propagation, isatty, context manager, exception safety).
- [ ] **Wiring** - Add integration tests for history.log creation in SessionOrchestrator (format correctness, validation failure logging, non-session mode, append mode, stdout restoration, Tee failure isolation).

## Implementation Notes
*(To be filled during implementation)*

## Implementation Plan
The implementation follows the task brief steps:
1. Create the Tee utility class in `src/teddy_executor/core/utils/io.py`.
2. Modify `session_orchestrator.py` to install the Tee at the start of `execute()` when in session mode, and ensure metadata header is printed to stdout.
3. Handle edge cases (validation failure, non-session, branching).
4. Add tests for Tee and SessionOrchestrator integration.

The Tee is a context manager that replaces `sys.stdout` with a custom writer that writes to both original stdout and the log file. It handles file open failures gracefully by logging a debug warning and skipping tee'ing.

Metadata header format:
```
[NN] <plan-title> | Waiting for <agent-name> to respond...
• Model: <model-string>
• Context: <current-context> / <max-context> tokens
• Session Cost: $<cost>
```

The turn number (NN) is extracted from the plan_path parent directory name. Plan title, agent name, model, context, and cost are available from the parsed plan, config, and session service after context preparation and before execution.

Key method: `SessionOrchestrator.execute()` installs Tee after determining `is_session` (after line ~30), wraps the rest of the method in try/finally to ensure Tee cleanup. The metadata header is printed after validation passes, before the actual execution call.

Test strategy:
- Tee unit tests: Verify write propagation, flush, isatty, context manager restore, exception safety.
- SessionOrchestrator tests: Use test doubles to simulate session turn execution and verify history.log creation and content.
- Integration: Run orchestration with mocked dependencies and assert file existence and format.
