# Bug: Session Plan Resolution Crash and Missing Logging

- **Status:** Unresolved
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [02-06-Orchestrator Hardening](/docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms

### 1. `FileNotFoundError` during `resume`
When resuming a session, specifically transitioning to a new turn (e.g., Turn 02), the system crashes with:
`BUG - Error: [Errno 2] No such file or directory: '.../02/plan.md'`

### 2. Missing Log
The "Checking configurations..." console message is visible during `teddy start` but absent during `teddy resume`.

## Context & Scope

### Regressing Delta
Recent hardening in Milestone 2 introduced automated turn transitions. The `SessionLifecycleManager` now handles the state machine between `EMPTY`, `PENDING_PLAN`, and `COMPLETE_TURN`.

### Environmental Triggers
- Running `teddy resume` on a session where a turn directory exists (e.g., `02/`) but the planning phase failed to produce a `plan.md` file.
- This can be triggered by LLM API timeouts or empty responses during the `PlanningService.generate_plan` phase.

### Ruled Out
- `SessionService.get_session_state` correctly identifies the state; however, the downstream `SessionOrchestrator` is too optimistic.

## Diagnostic Analysis

### Causal Model (Verified)
1.  **UI Level**: `handle_resume_session` calls `_run_cli_preflight_check` and `_echo_config_success` but omits the "Checking configurations..." status message present in `handle_new_session`.
2.  **Lifecycle Level**: `SessionLifecycleManager` identifies a turn as `PENDING_PLAN` if the directory exists and metadata doesn't indicate completion. It then calls `orchestrator.execute(plan_path=...)` assuming the file exists.
3.  **Orchestrator Level**: `SessionOrchestrator.execute` delegates to `_prepare_plan_parsing`.
4.  **Failure Point**: `_prepare_plan_parsing` evaluates `self._file_system_manager.read_file(plan_path)`. Since `read_file` maps to `pathlib.Path.read_text`, it raises `FileNotFoundError` if the file is missing, bypassing the internal structural validation and replanning logic.

### Discrepancies
- Missing `plan.md` in `PENDING_PLAN` state. The lifecycle manager assumes the planning phase successfully committed the file. (Resolved: The orchestrator should be the final gatekeeper for file existence before parsing).

### Investigation History
1. **CLI Analysis**: Confirmed `handle_resume_session` in `session_cli_handlers.py` is missing the `typer.echo("Checking configurations...", err=True)` call present in `handle_new_session`.
2. **Orchestrator Analysis**: Confirmed `SessionOrchestrator._prepare_plan_parsing` (line 200) calls `self._file_system_manager.read_file(plan_path)` without checking `path_exists`.
3. **MRE Verification**: Verified that calling `orchestrator.execute(plan_path=...)` with a non-existent file path results in a `FileNotFoundError` (reproduced in `spikes/debug/05-session-crash-mre.py`).
4. **Shadow Verification**: Implemented defensive check in `shadow_session_orchestrator.py` and verified via `spikes/debug/05-session-verify-shadow.py` that the orchestrator now triggers a re-plan instead of crashing.

## Solution
1.  **CLI Fix**: Updated `handle_resume_session` in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` to include the `typer.echo("Checking configurations...", err=True)` status message for parity with the `start` command.
2.  **Orchestrator Fix**: Updated `SessionOrchestrator._prepare_plan_parsing` in `src/teddy_executor/core/services/session_orchestrator.py` to check `self._file_system_manager.path_exists(plan_path)` before calling `read_file`.
3.  **Error Handling**: If the plan file is missing, the orchestrator triggers a re-plan loop with a descriptive error message ("Plan file not found: [path]"). This prevents a hard crash and leverages the existing automated recovery system.
4.  **Systemic Prevention**: Adopted a "Defensive Boundary" pattern. A systemic audit of `read_file` callers confirmed that while most services are defensive, Orchestrators require explicit pre-flight checks to maintain failure transparency.
