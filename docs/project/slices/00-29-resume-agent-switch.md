# Slice: resume-agent-switch
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:**
  - [CLI Adapter (inbound)](../../architecture/adapters/inbound/cli.md)
  - [SessionService (core/services/session_service.md)](../../architecture/core/services/session_service.md)
  - [ISessionManager (core/ports/outbound/session_manager.md)](../../architecture/core/ports/outbound/session_manager.md)
- **Scope Slug:** `resume-agent-switch`

## Business Goal
Allow users to change the AI agent persona mid-session by passing `-a/--agent` to `teddy resume`, permanently switching the session's agent for all future turns.

## Scenarios

> As a user, I want to resume a session with a different agent so that I can change the AI persona mid-conversation.

```gherkin
Scenario: Resume with new agent updates meta.yaml
  Given an existing session with agent "pathfinder"
  When the user resumes with "-a developer"
  Then the session's meta.yaml contains "agent_name: developer"
```

```gherkin
Scenario: Resume with new agent copies prompt file
  Given an existing session with agent "pathfinder"
  When the user resumes with "-a developer"
  Then the developer.xml prompt file exists in the session directory
```

```gherkin
Scenario: Resume with new agent overwrites old prompt file
  Given an existing session with agent "pathfinder"
  And a stale "assistant.xml" prompt file exists in the session directory
  When the user resumes with "-a developer"
  Then the old "assistant.xml" prompt file is removed
  And the new "developer.xml" prompt file exists in the session directory
```

```gherkin
Scenario: Resume without agent leaves session unchanged
  Given an existing session with agent "pathfinder"
  When the user resumes without "-a"
  Then the session's meta.yaml still contains "agent_name: pathfinder"
```

```gherkin
Scenario: Resume with nonexistent agent fails with clear error
  Given an existing session
  When the user resumes with "-a nonexistent"
  Then the user receives an error message that the agent prompt is not found
```

## Edge Cases
- **Case-insensitive agent name matching**: If `.teddy/prompts/` contains `Developer.xml` but user passes `-a developer`, the prompt should be found via casefold matching (mirrors existing `create_session` logic).
- **Stale prompt file with different stem**: If the session previously had a prompt file `assistant.xml` for agent "assistant" and user switches to "developer", the old `assistant.xml` must be removed to avoid stale prompt files.
- **No `.teddy/prompts/` directory**: If the prompts directory is missing, the call should fail with a clear error message indicating the agent prompt is not found.

## Key Unknowns
- [x] [Technical] **Prompt file naming convention**: `create_session` in `SessionService` already resolves prompt files via `Path(f).stem.casefold() == agent_name.casefold()` over `.teddy/prompts/` — confirmed by git grep. The same logic will be reused in `set_session_agent`.

## Implementation Plan
The implementation follows the Tracer Bullet Dependency Sequence:

1. **Contract** — Add `set_session_agent` method signature to `ISessionManager` protocol.
2. **Harness** — Add contract test for `set_session_agent` in `test_session_manager_contract.py`.
3. **Seam** — Implement `set_session_agent` in `SessionService` (real logic: update meta.yaml, copy/overwrite prompt XML, remove stale prompt files).
4. **Wiring** — Add `-a/--agent` parameter to `resume` CLI command, thread through `handle_resume_session`, call `ISessionManager.set_session_agent` before the turn loop.
5. **Logic** — Add unit tests for the resume agent switch behavior in `test_session_cli_handlers_resume_meta.py`.

No core domain changes beyond the protocol addition; the orchestrator and lifecycle manager automatically pick up the updated `meta.yaml` on each turn.

## Deliverables
- [x] **Contract** - Add `set_session_agent(session_name: str, agent_name: str) -> None` to the `ISessionManager` protocol.
- [ ] **Harness** - Add contract compliance test for `set_session_agent` in `test_session_manager_contract.py`.
- [ ] **Seam** - Implement `set_session_agent` in `SessionService` with full logic: update meta.yaml, copy/overwrite prompt, remove stale prompts.
- [ ] **Wiring** - Add `-a/--agent` to `teddy resume`, thread through `handle_resume_session`, call `container.resolve(ISessionManager).set_session_agent(...)` before `_orchestrate_session_loop`.
- [ ] **Logic** - Add unit tests in `test_session_cli_handlers_resume_meta.py` covering meta.yaml update, prompt copy, prompt overwrite, stale-prompt removal, no-flag-no-change, and nonexistent-agent error.

## Implementation Notes

### Contract — Add `set_session_agent` to `ISessionManager` protocol

- **Change:** Added `set_session_agent(session_name: str, agent_name: str) -> None` to the `@runtime_checkable ISessionManager` protocol, placed after `preserve_turn_in_session_context` (following the existing method ordering).
- **Test double:** Added the corresponding no-op implementation to `DummyManager` in the contract test file, placed after `preserve_turn_in_session_context` and before `get_cumulative_cost`. The no-op body (`return None`) is sufficient because the contract test only checks protocol compliance via `isinstance`, not behavioral correctness.
- **Verification:** Both contract tests pass (`2 passed`). Full suite green (`1633 passed, 5 skipped`).
- **Refactor:** No refactoring needed — the change is purely additive (one Protocol method + one test-double method) with zero risk to existing consumers.

## Verification
- [ ] `teddy resume -a developer` in an existing pathfinder session updates `agent_name` in `meta.yaml` to "developer"
- [ ] `teddy resume -a developer` copies `developer.xml` from `.teddy/prompts/` into the session directory, overwriting any existing prompt file
- [ ] `teddy resume` (without -a) behaves exactly as before — no meta.yaml changes, no prompt file changes
- [ ] `teddy resume -a nonexistent` fails with a clear error message that the agent prompt is not found
- [ ] All existing tests pass
- [ ] `uv run pytest tests/suites/unit/adapters/inbound/test_session_cli_handlers_resume_meta.py -v` passes
- [ ] `uv run pytest tests/suites/unit/core/ports/test_session_manager_contract.py -v` passes
