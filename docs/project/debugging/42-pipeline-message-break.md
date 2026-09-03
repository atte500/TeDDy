# Bug: Pipeline Mode Does Not Break on MESSAGE Action

- **Status:** Unresolved
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
The pipeline break logic relies on `report.action_logs` containing an `ActionLog` entry with `action_type == "MESSAGE"`. In the unit tests, synthetic `ActionLog` objects are injected. In real execution, the report is produced by `SessionOrchestrator.execute()` → `ExecutionOrchestrator.execute()` → `ExecutionReportAssembler.assemble()`. If the report's `action_logs` is empty, the `if pipeline and report.action_logs:` guard evaluates to `False`, skipping the break entirely. The loop then calls `orchestrator.resume()` again, which transitions to the next turn and prompts for user input.

**Hypothesis:** The first report returned by `orchestrator.resume()` has empty `action_logs`. This could happen if:
1. The `SessionOrchestrator.execute()` wraps the inner execution in a way that produces a different report.
2. The `SessionLifecycleManager._handle_planning_and_execution()` calls `orchestrator.execute()` but the returned report is restructured.
3. The MESSAGE action is executed but its `ActionLog` is not included in the report's `action_logs` for session-based execution.

### Discrepancies
- Unit tests show that when `action_logs` contains an `ActionLog` with `action_type="MESSAGE"`, the loop breaks. The real execution does not break, which means either `action_logs` is empty or the MESSAGE entry is missing.
- The agent's MESSAGE was printed to terminal (visible in output), confirming the MESSAGE action WAS executed. Yet the pipeline check didn't find it.

### Investigation History
1. **Hypothesis:** The `action_type` value in real execution differs from `"MESSAGE"`. **Observation:** `ActionDispatcher` sets `action_type = action_data.type` (from parsed plan, which is "MESSAGE"). The check `.upper() == "MESSAGE"` would match any casing. **Conclusion:** Unlikely cause.
2. **Hypothesis:** `report.action_logs` is empty because `SessionLifecycleManager._handle_planning_and_execution()` returns a report without action_logs. **Observation:** Read `session_lifecycle_manager.py`: the method calls `orchestrator.execute()` and returns the result. The orchestrator is `SessionOrchestrator`, which wraps `ExecutionOrchestrator.execute()`. That method populates `action_logs` via `_process_plan_actions`. **Conclusion:** Not confirmed, but plausible that `SessionOrchestrator.execute()` intercepts or modifies the report.
3. **Hypothesis:** The `SessionOrchestrator.execute()` returns a report with empty `action_logs` for the first turn due to session lifecycle handling. **Observation:** Read `session_orchestrator.py` lines 340-350: it accesses `report.action_logs` to check for empty user reply after communication turn. This implies the report SHOULD have action_logs. **Conclusion:** Inconclusive; the report should have action_logs, but the pipeline check still fails.

## Solution

(The root cause has not been definitively identified. The Debugger should:
1. Add a temporary print/log in `_orchestrate_session_loop` to dump the first report's `action_logs` content.
2. Run the manual pipeline test to see if action_logs is empty or if MESSAGE is missing.
3. If empty, trace back through `SessionOrchestrator.execute()` and `SessionLifecycleManager._handle_planning_and_execution()` to find where the action_logs are dropped.
4. If MESSAGE is present but not matching, inspect the actual action_type value.)
