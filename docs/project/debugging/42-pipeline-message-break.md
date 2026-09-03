# Bug: Pipeline Mode Does Not Break on MESSAGE Action

- **Status:** Resolved
- **Milestone:** N/A (ad-hoc slice)
- **Vertical Slice:** [Pipeline Automation](/docs/project/slices/00-18-pipeline-automation.md)
- **Specs:** [Pipeline Automation Task](/docs/project/tasks/pipeline-automation.md)

## Symptoms

### Expected Behavior
Running `teddy start -a assistant -p -m "Say hello and ask how I am"` should exit cleanly with code 0 after the agent issues its first `## Message`, without prompting for user input.

### Actual Behavior
The agent's MESSAGE is printed to terminal, but then the process prompts `"Response (type 'e' for editor) ›"` and waits for user input. Only after providing a reply does the process exit.

### Steps to Reproduce
1. Run: `teddy start -a assistant -p -m "Say hello and ask how I am"`
2. Observe: Agent responds with a message including `## Message`.
3. Observe: Process blocks on stdin with `"Response (type 'e' for editor) ›"` instead of exiting.
4. Provide input (e.g., "test"), then the process terminates.

## Context & Scope

### Regressing Delta
The change introduced in slice 00-18-pipeline-automation:
- Added `--pipeline` flag to `start()` in `__main__.py`.
- Added `pipeline` parameter to `handle_new_session()` and `_orchestrate_session_loop()` in `session_cli_handlers.py`.
- Added pipeline break logic: after each turn, scan `report.action_logs` for `action_type == "MESSAGE"`. If found, break the loop.

The break logic is in `_orchestrate_session_loop()`:
```python
if pipeline and report.action_logs:
    for log_entry in report.action_logs:
        action_type = getattr(log_entry, "action_type", None) or ""
        if action_type.upper() == "MESSAGE":
            break
    else:
        continue
    break
```

### Environmental Triggers
- Requires a real session (not unit test).
- Agent must produce a MESSAGE action (which the assistant does by default on first turn).
- Pipeline flag `-p` must be set.
- Initial message `-m` must be provided.

### Ruled Out
- The `-p` flag is correctly parsed and passed through (`interactive=False` is set based on `not (yolo or pipeline or ...)`).
- The unit tests for `_orchestrate_session_loop` pass with synthetic `ActionLog` objects.
- The `ActionDispatcher` correctly sets `action_type = action_data.type` for MESSAGE actions (value is "MESSAGE").
- The pipeline check logic is syntactically correct (for-else construct works correctly).
- `handle_report_output` does not mutate the report.

## Diagnostic Analysis

### Causal Model
The pipeline break check in `_orchestrate_session_loop` scans `report.action_logs` for a `MESSAGE` entry. Two independent empirical probes established:

1. **Inner execution chain (ExecutionOrchestrator):** The diagnostic MRE (`42-pipeline-message-mre.py`) proved that `ExecutionOrchestrator.execute()` with a `Plan` containing a single `MESSAGE` action produces a report with populated `action_logs` containing the `MESSAGE` entry (action_type="MESSAGE", details="Hello from pipeline test!"). This confirms the inner chain works correctly.

2. **Real pipeline execution:** The `ActionExecutor.confirm_and_dispatch()` method dispatches MESSAGE actions to the real `ActionFactory`, which binds `user_interactor.ask_question()` as the handler. In pipeline mode (`interactive=False`), `ask_question` blocks on standard input because no user is present to provide input. The action never completes, no `ActionLog` is ever produced, and the pipeline break check (which scans `report.action_logs` for MESSAGE) never triggers.

**Root Cause:** The `ActionExecutor.confirm_and_dispatch()` does not short-circuit MESSAGE actions when `interactive=False`. The condition `if interactive and not is_communication:` only skips interactive confirmation for non-MESSAGE actions; it does not prevent dispatch of MESSAGE actions. MESSAGE actions are still dispatched to `ActionFactory`, which calls `ask_question` (blocking on stdin). Thus, in real pipeline execution, the action hangs waiting for input and no ActionLog is appended to the report.

### Discrepancies
- Unit tests show that when `action_logs` contains an `ActionLog` with `action_type="MESSAGE"`, the loop breaks. The real execution does not break. **(Resolved: Unit tests mock `ask_question` to return a value immediately. In real pipeline execution, `ask_question` blocks because no user provides input.)**
- The agent's MESSAGE was printed to terminal (visible in output), confirming the MESSAGE action WAS executed. Yet the pipeline check didn't find it. **(Resolved: The MESSAGE action was dispatched and `ask_question` blocked on stdin. The action never completed, so no `ActionLog` was appended to `action_logs`. The pipeline check correctly found no MESSAGE entry.)**
- The inner execution chain MRE produced a valid ActionLog for MESSAGE even in interactive=False mode. **(Resolved: The MRE uses a `Mock` for `ask_question` that returns immediately, simulating unit test behavior. In real execution with `ConsoleInteractor`, `ask_question` blocks on stdin.)**

### Investigation History
1. **Hypothesis:** The `action_type` value in real execution differs from `"MESSAGE"`. **Observation:** `ActionDispatcher` sets `action_type = action_data.type` (from parsed plan, which is "MESSAGE"). The check `.upper() == "MESSAGE"` would match any casing. **Conclusion:** Unlikely cause.
2. **Hypothesis:** `report.action_logs` is empty because `SessionLifecycleManager._handle_planning_and_execution()` returns a report without action_logs. **Observation:** Read `session_lifecycle_manager.py`: the method calls `orchestrator.execute()` and returns the result. **Conclusion:** Not confirmed, but plausible.
3. **Hypothesis:** The `SessionOrchestrator.execute()` returns a report with empty `action_logs` for the first turn due to session lifecycle handling. **Observation:** Read `session_orchestrator.py` lines 340-350: it accesses `report.action_logs` to check for empty user reply after communication turn. This implies the report SHOULD have action_logs. **Conclusion:** Inconclusive.
4. **Hypothesis:** The inner execution chain (ExecutionOrchestrator) produces a correct report with MESSAGE in action_logs when `ask_question` returns immediately. **Observation:** MRE `42-pipeline-message-mre.py` confirms MESSAGE ActionLog is present when `ask_question` returns immediately (as in unit tests). **Conclusion:** Inner chain works; the issue must be in the real execution path where `ask_question` blocks.
5. **Hypothesis:** The real pipeline execution blocks because `ask_question` is called even in non-interactive mode. **Observation:** Trace through `ActionFactory._create_standard_action`: MESSAGE action is bound to `ask_question`. `ActionExecutor.confirm_and_dispatch` dispatches MESSAGE unconditionally when `interactive=False` because the condition `if interactive and not is_communication:` only skips interactive confirmation for non-MESSAGE actions; it does not skip dispatch for MESSAGE. **Conclusion:** Root cause confirmed: MESSAGE action is dispatched to `ask_question` which blocks in non-interactive mode.
6. **Hypothesis:** The fix: short-circuit MESSAGE actions in non-interactive mode before dispatch. **Observation:** Shadow file `shadow_action_executor.py` adds a guard `if is_communication and not interactive:` that creates a synthetic `ActionLog` with `details` from `action.params["content"]` and returns without dispatching. The shadow MRE (`42-pipeline-shadow-mre.py`) verifies:
   - MESSAGE ActionLog is present (action_type="MESSAGE", details="Hello from pipeline test!")
   - `ask_question` is NOT called (confirmed via mock assertion)
   - The pipeline break check would succeed.
   **Conclusion:** Fix verified.

## Solution

### Root Cause
The `ActionExecutor.confirm_and_dispatch()` method dispatches MESSAGE actions to the real `ActionFactory`, which binds `user_interactor.ask_question()` as the handler. In pipeline mode (`interactive=False`), this `ask_question` call blocks on standard input because no user is present to provide input. The action never completes, no `ActionLog` is produced, and the pipeline break check (which scans `report.action_logs` for MESSAGE) never triggers.
### Fix Proven

Add a `pipeline: bool = False` parameter to `ActionExecutor.confirm_and_dispatch()` and a guard clause:
```python
if is_communication and pipeline:
    content = action.params.get("content", action.params.get("prompt", ""))
    log_params = action.params.copy()
    if action.description:
        log_params["Description"] = action.description
    action_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params=log_params,
        details=content,
    )
    return (action_log, "")
```
This short-circuits MESSAGE actions only when `pipeline=True` (not in YOLO mode, which also sets `interactive=False`). The pipeline break check reads the synthetic ActionLog and breaks the loop. The `pipeline` flag is threaded through the orchestration chain: `_orchestrate_session_loop` → `SessionOrchestrator.resume()` → `SessionLifecycleManager.resume()` → `ExecutionOrchestrator.execute()` → `ActionExecutor.confirm_and_dispatch()`. All existing callers are unaffected because `pipeline` defaults to `False`.

### Preventative Measures
To prevent this class of assumption-driven interactive dependency in pipeline mode, introduce a systematic check:
- **All action handlers MUST declare an `interactive` parameter.** The `ActionFactory` should inspect whether the action handler requires stdin or user prompts and throw a clear error if invoked in non-interactive mode without a suitable fallback.
- **Implement a pipeline mode contract:** Any action type that requires user input must provide a fallback path (e.g., using default values or skipped action) when `interactive=False`. This can be enforced at the `ActionFactory` or `ActionDispatcher` level.
- **Add a regression test** that exercises the full `ActionExecutor` with a real `IUserInteractor` Mock that raises an exception on `ask_question` in pipeline mode, ensuring no action type blocks on stdin.
