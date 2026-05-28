# Slice: 01-03-CLI Flag Realignment

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Business Goal
Enable the `start` command to accept a `-c/--context` flag, allowing users (and agents) to seed new sessions with specific file paths or directories.

## Scenarios
> As a User, I want to provide specific context files when starting a session so that the AI is immediately oriented.

```gherkin
Given a project with files "src/main.py" and "docs/README.md"
When I run "teddy start -c src/main.py,docs/README.md"
Then a new session is created
And the "session.context" file contains both paths
```

## Edge Cases
- **Invalid Paths**: If a path provided in `-c` does not exist, the command should notify the user but proceed if other paths are valid.
- **Directory Expansion**: If a directory is provided, it should be expanded recursively (delegated to `ContextService`).

- **Component Docs:** [docs/architecture/core/ports/outbound/session_manager.md](/docs/architecture/core/ports/outbound/session_manager.md), [docs/architecture/core/services/session_service.md](/docs/architecture/core/services/session_service.md)

## Deliverables
- [ ] **Contract** - Update `ISessionManager.create_session` to accept `additional_context: Optional[list[str]] = None`.
- [ ] **Harness** - Create `tests/suites/acceptance/test_cli_context_flag.py` to verify `start -c` behavior.
- [ ] **Logic** - Update `SessionService.create_session` to merge `additional_context` into `session.context`.
- [ ] **Wiring** - Update `handle_new_session` in `session_cli_handlers.py` to accept `context: Optional[str] = None`.
- [ ] **Wiring** - Update `start` command in `src/teddy_executor/__main__.py` to include the `--context` flag.
