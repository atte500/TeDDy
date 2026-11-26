# Slice: Truthful Execution Order and Skipped-Action Reporting
- **Status:** Planned
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [IUserInteractor](/docs/architecture/core/ports/outbound/user_interactor.md), [ExecutionOrchestrator](/docs/architecture/core/services/execution_orchestrator.md), [IExecutionReportAssembler](/docs/architecture/core/ports/outbound/execution_report_assembler.md), [ExecutionReport](/docs/architecture/core/domain/execution_report.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `manual-execution-ordering`

## Goal
Make the console log and `report.md` describe what actually happened — every executed action in the order it ran, and every skipped action named with its reason — so a plan approved with deselections or partly executed by hand leaves an audit trail that matches reality.

## Context
- `IUserInteractor.notify_skipped_action(action, reason)` (`src/teddy_executor/core/ports/outbound/user_interactor.py`) is implemented in `ConsoleInteractorAdapter` but has **no call site anywhere** in `src/`, so deselected, halted, and interrupted actions are currently reported only through whatever status the report happens to carry.
- `ActionData` (`src/teddy_executor/core/domain/models/plan.py`): Carries `executed`, `state`, `action_log`, `selected`, `modified`, and `modified_fields`, but no execution-sequence field, so nothing records when an action ran relative to its siblings.
- `ExecutionOrchestrator`: Accumulates `action_logs` as it goes and hands them to the assembler, which copies them verbatim into the report, so the recorded order is the iteration order of the loop rather than the order the actions actually executed.
- Manual execution: The reviewer can execute a single action out of order (`textual_plan_reviewer_execution.py` builds a one-log report for the manual path), and on submit only the not-yet-executed actions run, so the loop's order diverges from the plan's order precisely in the case a user cares about.
- Both surfaces come from one list: the console log and the `report.md` action-log table both render from the assembled logs, which is why one ordering rule can serve both.
- Relationship to pruning: A pruned or halted turn must still name what was skipped, because an incomplete report that silently omits actions reads as success.

## Scenarios

> As a user reviewing a report, I want executed actions in the order they ran, not the order they were written.

```gherkin
Given a plan listing CREATE, EDIT, EXECUTE
When I execute the EXECUTE action manually first and then submit the plan
Then the report's action log lists EXECUTE first and CREATE and EDIT after it
And the console log shows the same order
```

> As a user, I want deselected actions named rather than silently missing.

```gherkin
Given a plan where I deselected two actions during review
When the plan finishes
Then the console names both skipped actions with the reason
And the report records them as skipped rather than omitting them
```

> As a user, I want a halt to name the actions it never reached.

```gherkin
Given a plan whose second action fails
When the run halts
Then the actions after it are named as skipped with the halt reason
```

## Edge Cases
- **All actions skipped**: If every action is deselected, then the run reports each skip and no execution log rows, because an empty action log must not read as a successful no-op.
- **Manual re-execution**: If the same action is executed manually twice, then only the last execution is recorded, because one action produced one outcome.
- **Message action**: If the plan contains a `MESSAGE` turn, then it is not reported as skipped, because a communicating turn was never meant to be executed.
- **Interrupted run**: If the run is interrupted mid-action, then the in-flight action is recorded as interrupted and everything after it as skipped, because the boundary must be visible.
- **Validation failure**: If validation rejects the plan before execution, then no skip notices are emitted, because nothing was consciously skipped.
- **Already-executed action**: If a submitted plan contains an action executed earlier in the session, then it is neither re-run nor reported as skipped, because it is not part of this run's work.
- **Reason collision**: If two different reasons apply (deselected and halted), then the one the user caused takes precedence, because the deselect is the more specific fact.

## Key Unknowns
- [ ] [Technical] Console log derivation: does the console output stream live as each action finishes, or is it rendered from the assembled logs? Design Sensitivity: if it streams live → the console order is already truthful and the slice only stamps and sorts the report, while the re-emit covers skips; if it renders from the assembled logs → one shared ordering key fixes both surfaces and the stamping deliverable owns the whole slice.

## Impact
1. `[EXTEND]` `ActionData` — carry an execution-sequence stamp recorded when the action starts, not when it was planned.
2. `[MIGRATE]` `ExecutionOrchestrator` — stamp on dispatch and order the assembled logs by sequence instead of iteration order.
3. `[MIGRATE]` The manual-execution path in the reviewer — stamp manually executed actions so they interleave correctly with the later batch.
4. `[WIRING]` The skip notices — call `notify_skipped_action` for every deselected, halted, and interrupted action, reusing the existing formatter rather than adding one.
5. `[MIGRATE]` `IUserInteractor`, `ExecutionOrchestrator`, and reviewer component pages — record the ordering rule and the skip-notice contract.

## Deliverables
- [ ] **Interface** — Add the execution-sequence field to `ActionData` with its "recorded on dispatch, never on parse" contract, so both the manual and the batch path can stamp it.
- [ ] **Harness** — Extend `ReportParser` so a test asserts the action-log order as structured data rather than by string position.
- [ ] **Core** — Stamp on dispatch in the orchestrator, order the assembled logs by stamp, and prove a manual-then-batch sequence end to end.
- [ ] **Wiring** — Emit `notify_skipped_action` for each deselected, halted, and interrupted action and prove the notices appear for all three reasons.
- [ ] **Cleanup** — Record the ordering rule and the skip-notice contract in the orchestrator, interactor, and reviewer component pages; remove the dead-port note if any page still describes the method as unused.

## Implementation Notes

## Verification
1. **Manual then batch:**
   Start a session, execute a middle action with `x`, then submit the plan.
   Verify the report lists that action first and the rest in plan order, and that the console matches.
2. **Deselection:**
   Deselect two actions and finish the run.
   Verify the console names both with their reason and the report marks them skipped.
3. **Halt:**
   Force an action failure in the middle of a plan.
   Verify the remaining actions are named as skipped with the halt reason.
