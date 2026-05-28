# Slice: 01-03-CLI Flag Realignment

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Business Goal
Enable the `start` command to accept a `-c/--context` flag and LLM overrides (`--model`, `--provider`, `--api-key`), ensuring full spec compliance and allowing users (and agents) to customize session-specific behavior.

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
- [ ] **Contract** - Update `ISessionManager.create_session` to accept `additional_context: Optional[list[str]] = None` and LLM overrides (`model`, `provider`, `api_key`).
- [ ] **Harness** - Create `tests/suites/acceptance/test_cli_context_flag.py` to verify `start -a`, `-m`, `-c`, and LLM overrides.
- [ ] **Logic** - Update `SessionService.create_session` to merge `additional_context` into `session.context` and persist overrides in `meta.yaml`.
- [ ] **Logic** - Update `PlanningService.generate_plan` to extract `provider` and `api_key` from metadata and pass them to `llm_client.get_completion`.
- [ ] **Wiring** - Update `handle_new_session` in `session_cli_handlers.py` to accept and pass the new flag values.
- [ ] **Wiring** - Fix `start` command in `src/teddy_executor/__main__.py`: explicitly add `-a` short flag for `--agent` and add `-c` for the new `--context` flag. Ensure `--model`, `--provider`, and `--api-key` are also wired.
- [ ] **Cleanup** - Verify through integration tests that all flags (including short aliases) are correctly propagated and persisted.
