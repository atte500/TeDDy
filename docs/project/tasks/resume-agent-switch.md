# Task: resume-agent-switch

## Business Goal
Allow users to change the AI agent persona mid-session by passing `-a/--agent` to `teddy resume`, permanently switching the session's agent for all future turns.

## Context
Currently `teddy start -a <agent>` creates a session with a specific agent. The agent name is stored in `meta.yaml` (`agent_name` key) and the agent's prompt XML is copied into the session directory. On `teddy resume`, the agent is read from `meta.yaml` and the prompt is loaded from the session's prompts directory on every turn automatically (via `SessionOrchestrator.execute()` which calls `self._lifecycle_manager.get_agent_name(plan_path)` which reads from `meta.yaml`).

The `resume` command currently has NO `-a/--agent` flag. This task adds it. When `-a <agent>` is provided:
1. The session's `meta.yaml` `agent_name` field is updated to the new agent name.
2. The new agent's prompt XML is copied from `.teddy/prompts/` into the session directory, **overwriting** any existing prompt file.
3. The orchestrator automatically picks up the change on subsequent turns — no changes to `SessionOrchestrator`, `SessionLifecycleManager`, or the turn loop are needed.

If `-a` is NOT provided, behavior is identical to current resume (unchanged).

## Implementation Steps

### Step 1: Add `-a/--agent` parameter to `resume` CLI command
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Add `agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Switch to a different agent persona for this session.")` to the `resume` function signature (around line 431). Pass `agent=agent` to `handle_resume_session` call at line 474.

### Step 2: Accept `agent` in `handle_resume_session` and call `set_session_agent` before the turn loop
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:**
  1. Add `agent: Optional[str] = None` parameter to `handle_resume_session` (function at line 959).
  2. After the `handle_resume_session` function resolves `session_name` (from `path` or latest session), and BEFORE calling `_orchestrate_session_loop`, add: `if agent: container.resolve(ISessionManager).set_session_agent(session_name, agent)`
  3. Add `from teddy_executor.core.ports.outbound.session_manager import ISessionManager` import if not already present.
  4. Thread the `agent` parameter through to `_echo_config_success` call if needed for display.

### Step 3: Add `set_session_agent` to `ISessionManager` protocol
- **File:** [src/teddy_executor/core/ports/outbound/session_manager.py](/src/teddy_executor/core/ports/outbound/session_manager.py)
- **Change:** Add the following method signature to the `ISessionManager` protocol class:

```python
def set_session_agent(self, session_name: str, agent_name: str) -> None:
    """
    Permanently changes the session's agent. Updates meta.yaml
    with the new agent_name and replaces the session's prompt
    XML with the new agent's prompt from .teddy/prompts/.
    """
    ...
```

### Step 4: Implement `set_session_agent` in `SessionService`
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Add the `set_session_agent` method to `SessionService`. The implementation should:
  1. Resolve the session root directory: `session_root = f".teddy/sessions/{session_name}"`
  2. Load the latest turn's meta.yaml via `load_turn_meta(self.get_latest_turn(session_name))` or directly read `session_root/meta.yaml` if it exists at root level. If neither, fall back to loading from turn 01: `load_turn_meta(f"{session_root}/01")`.
  3. Update `meta["agent_name"] = agent_name`
  4. Save the updated meta.yaml via `save_turn_meta(turn_dir, meta)`
  5. Find the new agent's prompt file in `.teddy/prompts/` (match by `Path(f).stem.casefold() == agent_name.casefold()` — mirroring the existing logic in `create_session`)
  6. Read the prompt content from `.teddy/prompts/{prompt_filename}`
  7. Write the prompt content to `{session_root}/{prompt_filename}`, overwriting any existing file with the same stem
  8. If a different prompt file existed previously (with a different stem), remove the old one to avoid stale prompt files

### Step 5: Add tests for resume agent switch behavior
- **File:** [tests/suites/unit/adapters/inbound/test_session_cli_handlers_resume_meta.py](/tests/suites/unit/adapters/inbound/test_session_cli_handlers_resume_meta.py)
- **Change:** Add tests for:
  1. `test_resume_with_new_agent_updates_meta_yaml` — Verify that passing `-a developer` to resume updates `meta.yaml`'s `agent_name` field.
  2. `test_resume_with_new_agent_copies_prompt` — Verify that the new agent's prompt XML is copied into the session directory.
  3. `test_resume_with_new_agent_overwrites_old_prompt` — Verify that the old prompt file is overwritten.
  4. `test_resume_without_agent_unchanged` — Verify that without `-a`, meta.yaml is NOT modified.

### Step 6: Add `ISessionManager` contract test for `set_session_agent`
- **File:** [tests/suites/unit/core/ports/test_session_manager_contract.py](/tests/suites/unit/core/ports/test_session_manager_contract.py)
- **Change:** Add a test for the new protocol method to ensure contract compliance.

## Verification
1. `teddy resume -a developer` in an existing pathfinder session should:
   - Update `agent_name` in `meta.yaml` to "developer"
   - Copy `developer.xml` from `.teddy/prompts/` into the session directory
   - All subsequent turns use the developer prompt
2. `teddy resume` (without `-a`) should behave exactly as before — no meta.yaml changes, no prompt file changes
3. `teddy resume -a nonexistent` should fail with a clear error message that the agent prompt is not found
4. All existing tests should pass
5. Run: `uv run pytest tests/suites/unit/adapters/inbound/test_session_cli_handlers_resume_meta.py -v`
6. Run: `uv run pytest tests/suites/unit/core/ports/test_session_manager_contract.py -v`
