# Slice: Pipeline Automation Flag (`--pipeline`)

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc slice)
- **Specs:** [Pipeline Automation Task](/docs/project/tasks/pipeline-automation.md)
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [Session CLI Handlers](/docs/architecture/adapters/inbound/session_cli_handlers.md)
- **Scope Slug:** `pipeline-automation`

## Business Goal

Enable TeDDy to run autonomously in automated pipelines (e.g., bash loops, CI, Makefiles) by adding a `--pipeline` flag that auto-approves all actions, requires an initial message, and cleanly exits as soon as the agent issues a `## Message`.

## Scenarios

> As a developer, I want to run TeDDy in a CI pipeline without manual interaction, so that I can automate code generation tasks.

```gherkin
Scenario: Pipeline mode enforces initial message
  Given TeDDy is invoked with `teddy start --pipeline`
  When no `-m` argument is provided
  Then TeDDy raises a ValueError with message "Pipeline mode requires an initial message via -m/--message."
  And no session is created

Scenario: Pipeline mode exits cleanly after first agent message
  Given TeDDy is invoked with `teddy start -a assistant -p -m "Say hello"`
  When the agent completes its first turn
  And the report contains a MESSAGE action
  Then the session loop breaks
  And the process exits with code 0
```

## Edge Cases

- **Missing -m in pipeline mode:** If `--pipeline` is set without `-m`, the tool must error immediately without creating a session.
- **Non-pipeline mode unchanged:** Existing behavior with `-y` or interactive mode must not be affected; no MESSAGE scanning must occur.
- **Pipeline mode without MESSAGE:** If the agent does not emit a `## Message`, the loop should continue normally (same as non-pipeline behavior).
- **Compound action logs:** MESSAGE detection should be case-insensitive and match any action log entry with action_type "MESSAGE".

## Key Unknowns

- [x] [Technical] How to break the session loop after detecting a MESSAGE action without modifying inner services. – Use the existing report.action_logs after each turn; no need to touch SessionOrchestrator.
- [x] [Functional] Should `--pipeline` imply `--yolo`? – Yes, pipeline mode implicitly sets interactive=False (no need to also pass -y).

## Implementation Plan

The feature is purely additive to the CLI wiring layer. No changes to core services are required.

1. Add `--pipeline` flag to the `start` command in `__main__.py`.
2. Pass `pipeline` through `handle_new_session` to `_orchestrate_session_loop`.
3. In `handle_new_session`, enforce that `pipeline` requires `-m`.
4. In `_orchestrate_session_loop`, after each report, scan `action_logs` for MESSAGE type; if found, break the loop.
5. Write unit tests verifying the new behavior.

## Deliverables

- [ ] **Wiring** – Add `--pipeline` flag, parameter propagation, enforcement of `-m`, and loop exit on MESSAGE. Includes unit tests for the new behavior.

## Implementation Notes

(To be filled during implementation.)

## Verification

1. [ ] Unit test: `handle_new_session` with `pipeline=True` and no `-m` raises ValueError.
2. [ ] Unit test: `_orchestrate_session_loop` with `pipeline=True` and report containing MESSAGE action breaks after one turn.
3. [ ] Unit test: `_orchestrate_session_loop` with `pipeline=True` but no MESSAGE in report does NOT break (continues loop).
4. [ ] Unit test: Non-pipeline mode (pipeline=False) ignores MESSAGE detection (behavior unchanged).
5. [ ] Manual smoke test: `teddy start -a assistant -p -m "Say hello and ask how I am"` exits cleanly after first ## Message.
6. [ ] Manual error test: `teddy start -a assistant -p` shows error and exits.
7. [ ] Regression test: `teddy start -a assistant -m "Say hello" -y` works as before.
