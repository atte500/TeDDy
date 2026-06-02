# Slice: 02-03-Safety Limits

- **Status:** In Progress
- **Prototype:** [spikes/prototypes/02-03-safety-limits.py](/spikes/prototypes/02-03-safety-limits.py)
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
- [x] **Cleanup** - Fix `PLR0915` (Too many statements) in `session_cli_handlers.py` [DEBT].
- [x] **Contract** - Update `ISessionLoopGuard.should_continue` signature to include `cumulative_cost` and `interactive` flag.
- [ ] **Harness** - Create `MockSessionLoopGuard` for testing limit breaches.
- [ ] **Seam** - Update `ProductionSessionLoopGuard` to store `initial_turn` and `initial_cost` on instantiation.
- [ ] **Logic** - Implement `yolo_guardrails` enforcement in `ProductionSessionLoopGuard`.
- [ ] **Logic** - Implement `migrate_to_continuation` in `SessionService` for the Turn 99 -> 100 transition.
- [ ] **Logic** - Implement Message Turn protection in `SessionPruningService` (check for `## Message` + `status != FAILURE`); make it configurable via `auto_pruning.preserve_message_turns` (default: `true`).
- [ ] **Logic** - Relocate `system_prompt.xml` to session root in `SessionService.create_session`.
- [ ] **Logic** - Refactor `PromptManager` and `PlanningService` to resolve system prompts exclusively from the session root.
- [ ] **Wiring** - Update `config.yaml` with `yolo_guardrails` keys.
- [ ] **Wiring** - Update `SessionOrchestrator` to pass the `interactive` flag to the loop guard.

## Implementation Notes
- **CLI Refactor**: Extracted `_orchestrate_session_loop` in `session_cli_handlers.py` to resolve `PLR0915` (Too many statements) and eliminate duplication between `start` and `resume` logic.
- **Mocking Protocol**: Use `unittest.mock.create_autospec` for port mocks in unit tests to ensure signature drift is caught immediately during contract updates.
- **Harness Repair**: Systemic regressions in acceptance/integration tests during the `ISessionLoopGuard` contract update were traced to the `TestEnvironment` harness, which required a matching signature update for its default mock side-effect.
- **Prototype Scope**: The validated prototype (`spikes/prototypes/02-03-safety-limits.py`) focused strictly on the "Centennial" migration boundary and pruning logic. It did not simulate physical directory creation for every incremental turn (T1-T98), as that logic already exists in the production `SessionRepository`.
- **System Prompt Relocation**: Prototyper confirmed that moving the agent's dynamic prompt (e.g., `pathfinder.xml`) to the session root simplifies migration, as it only needs to be copied once per centennial jump rather than once per turn.
- **Pruning Logic**: Successful `## Message` turns are now protected from pruning by checking for the presence of the message header and a `SUCCESS` status in the report.

## Implementation Plan
### Delta Analysis
1.  **Safety Limits (Loop Guard)**:
    -   **Target**: `src/teddy_executor/core/ports/outbound/session_loop_guard.py` & `src/teddy_executor/core/services/session_loop_guard.py`.
    -   **Delta**: Update `should_continue` signature to `should_continue(self, turn_count: int, cumulative_cost: float, interactive: bool)`.
    -   **Delta**: Update `ProductionSessionLoopGuard` to capture `_start_turn` and `_start_cost` in `__init__`.
    -   **Delta**: Enforce process-relative limits (`turn_count - _start_turn` and `cumulative_cost - _start_cost`) against `yolo_guardrails` config if `interactive` is False.
2.  **Session Migration (Session Service)**:
    -   **Target**: `src/teddy_executor/core/services/session_service.py`.
    -   **Delta**: Implement `_migrate_to_continuation(self, cur_dir: Path, meta: Dict) -> str`.
    -   **Delta**: Use `re.search(r"-(\d+)$", name)` to detect and increment session suffixes.
    -   **Delta**: Clone `session.context` and the active `{agent_name}.xml` prompt from the old session root to the new session root.
    -   **Delta**: Reset Turn ID to `01` in the new session.
3.  **Pruning Discrimination (Pruning Service)**:
    -   **Target**: `src/teddy_executor/core/services/session_pruning_service.py`.
    -   **Delta**: In `_identify_turns_to_prune`, add a check for `## Message`.
    -   **Delta**: If a turn's `plan.md` contains `## Message` and its `report.md` is NOT a validation failure or error, explicitly `continue` to spare both from the `turns_to_prune` map.
    -   **Delta**: Ensure `_process_context_item` preserves both the plan and report for spared turns.
4.  **Architecture Polish**:
    -   **Target**: `src/teddy_executor/core/services/session_service.py`.
    -   **Delta**: In `create_session`, change the prompt write destination from `turn_dir` to `session_root`.
    -   **Delta**: In `transition_to_next_turn`, remove the call to `self._repository.copy_prompt`.
    -   **Target**: `src/teddy_executor/core/services/prompt_manager.py`.
    -   **Delta**: Update `fetch_system_prompt` to check `turn_path.parent / f"{agent_name}.xml"` as the primary location for session prompts.

### Actionable Strategy
1. **Targeted Integrity Audit**: Audit `SessionLoopGuard`, `SessionService`, and `SessionPruningService`.
2. **Limit Logic**: Weaponize the loop guard with process-relative tracking.
3. **Migration Logic**: Implement the Turn 100 trigger and session cloning.
4. **Pruning Polish**: Add the successful message-turn exception to the pruning logic.
5. **Prompt Relocation**: Execute the hard cutover of `system_prompt.xml` from turns to the session root.
