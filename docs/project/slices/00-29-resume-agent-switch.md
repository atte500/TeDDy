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
- [x] **Harness** - Add contract compliance test for `set_session_agent` in `test_session_manager_contract.py`.
- [x] **Seam** - Implement `set_session_agent` in `SessionService` with full logic: update meta.yaml, copy/overwrite prompt, remove stale prompts.
- [x] **Wiring** - Add `-a/--agent` to `teddy resume`, thread through `handle_resume_session`, call `container.resolve(ISessionManager).set_session_agent(...)` before `_orchestrate_session_loop`.
- [ ] **Logic** - Add unit tests in `test_session_cli_handlers_resume_meta.py` covering meta.yaml update, prompt copy, prompt overwrite, stale-prompt removal, no-flag-no-change, and nonexistent-agent error.

## Implementation Notes

### Contract — Add `set_session_agent` to `ISessionManager` protocol

- **Change:** Added `set_session_agent(session_name: str, agent_name: str) -> None` to the `@runtime_checkable ISessionManager` protocol, placed after `preserve_turn_in_session_context` (following the existing method ordering).
- **Test double:** Added the corresponding no-op implementation to `DummyManager` in the contract test file, placed after `preserve_turn_in_session_context` and before `get_cumulative_cost`. The no-op body (`return None`) is sufficient because the contract test only checks protocol compliance via `isinstance`, not behavioral correctness.
- **Verification:** Both contract tests pass (`2 passed`). Full suite green (`1633 passed, 5 skipped`).
- **Refactor:** No refactoring needed — the change is purely additive (one Protocol method + one test-double method) with zero risk to existing consumers.

### Harness — Contract compliance test for `set_session_agent`

- **Status:** Already covered by existing infrastructure.
- **Rationale:** The existing `test_session_manager_contract_accepts_new_parameters` test checks `isinstance(DummyManager(), ISessionManager)`. Since `@runtime_checkable` protocols verify all required members at runtime, and `DummyManager` now includes `set_session_agent`, this test already covers the new method. No additional test code was required.
- **Verification:** Both contract tests pass (`2 passed`). Full suite green (`1633 passed, 5 skipped`).

### Seam — Implement `set_session_agent` in `SessionService`

- **Change:** Added `set_session_agent` method to `SessionService` ([session_service.py](/src/teddy_executor/core/services/session_service.py)) with full logic:
    1. Resolve latest turn via `self.get_latest_turn(session_name)`
    2. Load meta.yaml via `self.load_turn_meta`, update `agent_name`, save via `self.save_turn_meta`
    3. Find new prompt in `.teddy/prompts/` via `_resolve_agent_prompt` (casefold stem matching)
    4. Write new prompt to session root, overwriting any file with same stem
    5. Remove stale prompt files: list session root, for each file whose stem casefold-matches a known prompt from `.teddy/prompts/` but does NOT match the new agent's stem, call `remove_file`
- **Prerequisite:** `remove_file` was added to `IFileSystemManager` protocol, `LocalFileSystemAdapter`, and the adapter contract test before the stale-removal step (interleaved protocol expansion).
- **Refactor:** Extracted `_resolve_agent_prompt(agent_name) -> tuple[str, str]` from both `create_session` and `set_session_agent` into a shared helper, eliminating ~40 lines of duplicated prompt-resolution + error-message code. The helper is placed after `_initialize_meta_data` and before `get_latest_turn`.
- **Tests:** Two tests added in [test_session_service.py](/tests/suites/unit/core/services/test_session_service.py):
    - `test_set_session_agent_updates_meta_yaml_and_copies_prompt` — asserts meta.yaml update and new prompt write.
    - `test_set_session_agent_removes_stale_prompt_files` — asserts stale prompt removal, non-prompt files preserved.
- **Cycle:** Red → Green → Refactor. Red confirmed `AttributeError` (method missing); Green passed both tests; Refactor extracted the helper.
- **Verification:** Full suite green (`1637 passed, 5 skipped`).

### Wiring — Add `-a/--agent` to `teddy resume` CLI command

- **Changes:**
    1. Added `agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Switch to a different agent persona for this session.")` to the `resume` function in [__main__.py](/src/teddy_executor/__main__.py), placed after `--api-key` and before `--message`.
    2. Added `agent` parameter to `handle_resume_session` signature in [session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py), placed after `api_key` and before `message`.
    3. Added the `ISessionManager` import to `session_cli_handlers.py` (already present from existing usage — confirmed via `git grep`).
    4. Inserted the agent-switch call after `_sync_and_display_session_meta` and before `_orchestrate_session_loop`:
       ```python
       if agent:
           container.resolve(ISessionManager).set_session_agent(session_name, agent)
       ```
    5. Passed `agent=agent` from `__main__.py`'s `handle_resume_session(...)` call.
    6. **Refactor:** Fixed an unintended `setup_api_key` regression introduced during the `agent` threading (the call was changed to `_resolve_setup_api_key(interactive)` with wrong arity); restored it to `_resolve_setup_api_key(system_env, pipeline=pipeline)`.
- **Tests:** One test added in [test_session_cli_handlers.py](/tests/suites/unit/adapters/inbound/test_session_cli_handlers.py):
    - `test_resume_handler_calls_set_session_agent_when_agent_provided` — verifies that passing `agent` to `handle_resume_session` calls `ISessionManager.set_session_agent` with the correct session name and agent name.
- **Cycle:** Red → Green → Refactor. Red confirmed `TypeError: unexpected keyword argument 'agent'`. Green passed after adding the parameter and the call. Refactor fixed the `setup_api_key` arity regression (unintended change from `system_env, pipeline=pipeline` to `interactive`).
- **Verification:** Full suite green (`1638 passed, 5 skipped`).

## Verification
- [ ] `teddy resume -a developer` in an existing pathfinder session updates `agent_name` in `meta.yaml` to "developer"
- [ ] `teddy resume -a developer` copies `developer.xml` from `.teddy/prompts/` into the session directory, overwriting any existing prompt file
- [ ] `teddy resume` (without -a) behaves exactly as before — no meta.yaml changes, no prompt file changes
- [ ] `teddy resume -a nonexistent` fails with a clear error message that the agent prompt is not found
- [ ] All existing tests pass
- [ ] `uv run pytest tests/suites/unit/adapters/inbound/test_session_cli_handlers_resume_meta.py -v` passes
- [ ] `uv run pytest tests/suites/unit/core/ports/test_session_manager_contract.py -v` passes
