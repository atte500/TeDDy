# Slice: 02-03-Safety Limits

- **Status:** Planned
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Ensure system safety by enforcing cost and turn limits in automated (YOLO) mode and provide a seamless continuation when turn limits are reached.

## Scenarios
> As a user running in YOLO mode, I want the system to stop if it exceeds 99 turns or $5.00 in costs so that I don't incur unexpected charges or get stuck in infinite loops.
```gherkin
Given a session running with --yolo
And yolo_guardrails.max_turns is set to 5
When the 6th turn is reached since the process started
Then the loop guard should terminate the session
And a warning should be displayed
```

> As a user, I want my session to automatically migrate to a new folder when Turn 99 is finished so that I can continue working without manually resetting the context.
```gherkin
Given a session currently at Turn 99
When I execute Turn 99 successfully
Then the system should create a new session directory "{session_name}-2"
And it should copy session.context and system_prompt.xml to the new root
And it should transition Turn 99's turn.context to Turn 01 of the new session
```

## Edge Cases
- **Resume with Limits**: If I resume a session, the limits (turns/cost) apply incrementally to the *current* process run, not the session history.
- **Validation Failure Pruning**: Message turns that failed validation must NOT be protected by the pruning exception.
- **Migration with Suffix**: If migrating `{name}-2`, the next session should be `{name}-3`.

## Deliverables
- [ ] **Contract** - Update `ISessionLoopGuard.should_continue` signature to include `cumulative_cost` and `interactive` flag.
- [ ] **Harness** - Create `MockSessionLoopGuard` for testing limit breaches.
- [ ] **Seam** - Update `ProductionSessionLoopGuard` to store `initial_turn` and `initial_cost` on instantiation.
- [ ] **Logic** - Implement `yolo_guardrails` enforcement in `ProductionSessionLoopGuard`.
- [ ] **Logic** - Implement `migrate_to_continuation` in `SessionService` for the Turn 99 -> 100 transition.
- [ ] **Logic** - Implement Message Turn protection in `SessionPruningService` (check for `## Message` + `status != FAILURE`).
- [ ] **Logic** - Relocate `system_prompt.xml` to session root in `SessionService.create_session`.
- [ ] **Logic** - Refactor `PromptManager` and `PlanningService` to resolve system prompts exclusively from the session root.
- [ ] **Wiring** - Update `config.yaml` with `yolo_guardrails` keys.
- [ ] **Wiring** - Update `SessionOrchestrator` to pass the `interactive` flag to the loop guard.

## Implementation Plan
1. **Targeted Integrity Audit**: Audit `SessionLoopGuard`, `SessionService`, and `SessionPruningService`.
2. **Limit Logic**: Weaponize the loop guard with process-relative tracking.
3. **Migration Logic**: Implement the Turn 100 trigger and session cloning.
4. **Pruning Polish**: Add the successful message-turn exception to the pruning logic.
5. **Prompt Relocation**: Execute the hard cutover of `system_prompt.xml` from turns to the session root.
