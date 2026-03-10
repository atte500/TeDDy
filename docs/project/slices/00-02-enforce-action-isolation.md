# Vertical Slice: Enforce Soft Action Isolation

## Business Goal
To ensure system state consistency by preventing terminal actions (PROMPT, INVOKE, RETURN) from executing when they are combined with other actions in a single plan.

## Acceptance Criteria

### Scenario 1: Isolated Terminal Action executes normally [✓]
Given a plan with a single action of type `PROMPT`
When `teddy execute` is run
Then the `PROMPT` action should be executed.

### Scenario 2: Terminal Action is skipped in multi-action plan [✓]
Given a plan with a `CREATE` action and a `PROMPT` action
When `teddy execute` is run
Then the `CREATE` action should be executed normally
And the `PROMPT` action should be marked as `SKIPPED`
And the skip reason should be: "Action must be executed in isolation to ensure state consistency."

### Scenario 3: Handoff actions are skipped in multi-action plan [✓]
Given a plan with an `EXECUTE` action and an `INVOKE` action
When `teddy execute` is run
Then the `EXECUTE` action should be executed normally
And the `INVOKE` action should be marked as `SKIPPED`
And the skip reason should match Scenario 2.

## Architectural Changes
- **ExecutionOrchestrator:** Modify the action execution loop in `src/teddy_executor/core/services/execution_orchestrator.py` to check for terminal action isolation. [✓]
- **Terminal Action Registry:** Define a list of terminal action types (`prompt`, `invoke`, `return`). [✓]

## Deliverables
- [✓] Updated `ExecutionOrchestrator` to detect and skip non-isolated terminal actions.
- [✓] Integration tests in `tests/integration/core/services/test_execution_orchestrator.py` verifying the skip logic.
- [✓] Acceptance test in `tests/acceptance/test_action_isolation.py` verifying the end-to-end behavior and the specific skip reason string.
