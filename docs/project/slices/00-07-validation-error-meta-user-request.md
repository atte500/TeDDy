# Slice: Validation Error User Request Fix
- **Status:** Planned
- **Milestone:** [/docs/project/milestones/10-interactive-session-and-config.md](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [/docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Showcase:** N/A
- **Component Docs:** [/docs/architecture/core/services/session_service.md](/docs/architecture/core/services/session_service.md), [/docs/architecture/core/services/planning_service.md](/docs/architecture/core/services/planning_service.md)

## Business Goal
Ensure that in the stateful multi-turn session workflow, when an automated plan validation failure occurs, the resulting automated validation feedback message is never recorded as the manual human prompt (`user_request`) in the next turn's metadata (`meta.yaml`). The original human prompt of the parent turn must be carried forward and preserved throughout the automated replan loop.

## Scenarios
> As a developer using stateful session turns, I want the session's metadata ledger to accurately reflect my actual manual prompts, so that my turn history, audit logs, and LLM context are never polluted by automated system feedback messages during plan validation failures.

```gherkin
Scenario: Normal turn preserves manual human prompt
  Given a new session turn "02"
  When the planning service generates a plan for turn "02" with manual prompt "Implement feature X"
  Then the metadata for turn "02" should save "user_request" as "Implement feature X"
  And the metadata for turn "02" should not contain "is_replan"

Scenario: Automated validation replan turn carries forward and preserves parent prompt
  Given a plan in turn "02" that failed logical validation
  And turn "02" has metadata with "user_request" set to "Implement feature X"
  When the system transitions to next turn "03" with validation failure status
  Then the metadata for turn "03" should be initialized with "is_replan: True"
  And the metadata for turn "03" should carry forward "user_request" as "Implement feature X"
  When the planning service generates a corrected plan for turn "03" with automated feedback message "The previous plan failed validation..."
  Then the metadata for turn "03" should preserve "user_request" as "Implement feature X"
```

## Edge Cases
- **[No Parent User Request]**: If a parent turn has no manual `user_request` saved in its metadata (e.g., due to custom external manipulation), then the replan turn should not initialize it, in order to prevent creating invalid or spurious fields.
- **[Multiple Replan Loops]**: If validation fails multiple times consecutively (turn 2 fails, replan turn 3 fails, replan turn 4 is generated), then each subsequent turn must continue to carry forward `is_replan: True` and the original parent `user_request`, in order to maintain structural audit integrity across multiple recovery attempts.

## Deliverables
Checklist of atomic units of work ordered following the Deliverable Dependency Sequence:

- [x] **Contract** - Update `ISessionManager.transition_to_next_turn` interface to ensure any override specifications are consistent with carrying forward metadata.
- [x] **Logic** - Edit `SessionService.transition_to_next_turn` implementation to accept `is_validation_failure: bool` and propagate `is_replan: True` plus `user_request` into the new turn's metadata during transition.
- [ ] **Logic** - Edit `PlanningService.generate_plan` to inspect the turn's `meta.yaml` and suppress overwriting `user_request` with the LLM prompt if `is_replan: True` is present.
- [ ] **Wiring** - Ensure standard integration test suite executes and asserts both normal transitions and validation-triggered transitions behave correctly.

## Implementation Notes
- The fix has been verified via a Minimal Reproducible Example (`spikes/debug/01-validation-error-meta-user-request-mre.py`) running against shadow service classes.
- Standard dependency injection patterns (Constructor Injection) are maintained, with zero coupling to any runtime container frameworks.
- **SessionService metadata propagation**: Passed `is_validation_failure` from `transition_to_next_turn` down into `_persist_next_meta`. Updated `_persist_next_meta` to append `is_replan: True` and carry forward `user_request` from parent metadata when validation fails, while ensuring fields are omitted if parent has no such metadata. Verified using robust unit tests in `tests/suites/unit/core/services/test_session_service_transition.py`.

## Implementation Plan
1. Update `SessionService.transition_to_next_turn` and its private helper `_persist_next_meta` to accept and handle `is_validation_failure`.
2. Update `PlanningService.generate_plan` to conditionally skip updating `meta["user_request"]` if `meta.get("is_replan")` evaluates to `True`.
3. Verify that all standard tests in `tests/suites/integration/core/services/test_session_orchestrator_validation.py` continue to pass.
