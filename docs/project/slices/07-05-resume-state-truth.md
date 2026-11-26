# Slice: Resume-State Single Source of Truth
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** [06-01-literal-helper-single-sourcing](./06-01-literal-helper-single-sourcing.md), [06-07-user-request-render-alignment](./06-07-user-request-render-alignment.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [ISessionManager](/docs/architecture/core/ports/outbound/session_manager.md), [SessionService](/docs/architecture/core/services/session_service.md)
- **Scope Slug:** `resume-state-truth`

## Goal
Make one recorded state decide what `resume` does, so a communicating turn stopped by a pipeline run and one stopped by an interrupt are handled by the same branch instead of one being recorded and the other guessed from the pending plan's shape.

## Context
- The defect is measured, and the code states it. `awaiting_reply` has exactly one writer in `src`: `session_orchestrator.py:367` sets it and `:368` saves it, reached only through `_is_pipeline_message_stop` (`:417-441`), which returns `False` outright when `not pipeline`. An interactively interrupted communicating turn therefore leaves no record at all.
- The sole reader reconstructs the missing record from plan shape. `_should_consume_awaiting_reply` (`session_lifecycle_manager.py:308-322`) returns `bool(turn_meta.get("awaiting_reply")) or (plan is not None and plan.is_communication_turn())`, and its docstring says a reply is consumed "when the turn carries the ``awaiting_reply`` flag (pipeline stop) or when the parsed pending plan is a MESSAGE-only communication turn (an interactively-interrupted communication turn lacks the flag but is semantically awaiting a reply)." That sentence is the defect written by its author.
- The cost is a silent coupling rather than a visible break. Any change to `Plan.is_communication_turn()` or to the ordering of the resume verdict tree changes interrupt-resume behaviour with no test naming it, because the inference is what the tests exercise; the pipeline path keeps working either way, which is what makes the divergence invisible in review.
- The interrupt is observed outside core. `_orchestrate_session_loop` catches `KeyboardInterrupt` at `session_cli_handlers.py:667` under an explicit immediate-exit contract, so session-metadata I/O must not be added there. Recording belongs on the core side of the boundary that already decides whether a turn communicates (`session_orchestrator.py:333`).
- `is_communication_turn` has six `src` call sites and only `session_lifecycle_manager.py:321` is a resume-intent signal. `:190` classifies hard-kill recovery, `execution_orchestrator.py:49`/`:191` and `session_orchestrator.py:333`/`:435` are render and pipeline-stop decisions, and `session_cli_handlers.py:550` is a separate report-based predicate for the guardrail baseline reset. The prune deliverable names one line, not a category.
- Requirement 8 is already delivered and must not be re-litigated here. The `PENDING_PLAN` non-awaiting branch seeds `plan.metadata["user_request"] = message` (`:126-134`), the unparseable path appends the reply to the re-executed turn's report through `_record_reply_on_resumed_turn` (`:142`, `:324-349`), a marked hard-killed turn recovers through `_recover_interrupted_turn` (`:491-521`), and `tests/suites/unit/core/services/test_session_lifecycle_pending_plan_non_communication_resume.py` pins all of it. The as-built rule is forward-into-execution, so this slice's only obligation there is a regression test that survives its own rewrite of the same branch.
- Dependencies are hard, not incidental. [06-01](./06-01-literal-helper-single-sourcing.md) single-sources the `awaiting_reply` key, so this slice writes a constant rather than a literal. [06-07](./06-07-user-request-render-alignment.md) rewrites the `## User Request` fence and its sanitizer, and both `_append_user_request` and `_record_reply_on_resumed_turn` write exactly that section through `embed_in_fence(message, 'text')`, so the regression test must pin 06-07's fence rather than today's bytes.
- Durability precondition: the state lives in `meta.yaml`, so [07-01](./07-01-durable-session-metadata.md) is what keeps a hard kill from losing the record and reinstating the inference; that ordering is enforced by 07-01's own prerequisite chain rather than by a third prerequisite here.
- Boundary: recording is a persistence concern on the session contract, not an orchestrator detail. The orchestrator decides *when* a communicating turn stopped; the lifecycle manager decides *what* a recorded state implies. Keeping those apart is what lets the behaviour be tested without a running session.

## Scenarios

> As a user, I want an interrupted reply prompt to survive a resume.

```gherkin
Given a communicating turn interrupted before it could finalize
When the session is resumed
Then the interruption's own recorded state drives the resume
And plan shape is not consulted to decide that the turn was waiting
And the operator is prompted for the reply
```

> As a user, I want a pipeline-stopped turn to resume exactly as it does today.

```gherkin
Given a communicating turn stopped by a pipeline run
When the session is resumed
Then the recorded state is the one the pipeline stop wrote
And the reply path behaves identically to the pre-change run
```

> As a maintainer, I want one branch instead of two meanings.

```gherkin
Given both stop paths for a communicating turn
When each records its state
Then both records are identical
And a single resume branch reads them
```

> As a user, I want the delivered pending-reply behaviour to stay delivered.

```gherkin
Given a session paused on a non-communication pending plan
When it is resumed with a replacement instruction
Then the instruction still reaches the turn it reached before this slice
And the User Request section still carries it under the shared fence rule
```

## Edge Cases
- **Both stop paths**: If the pipeline stops the turn or an interrupt stops it, then the same record is written by both, because a differing record is the defect being removed.
- **Interrupt before the plan is known**: If the interrupt arrives before the plan is parsed, then the plan's shape is unknown and no state is recorded; the turn is genuinely not awaiting a reply, and the resume tree falls through to re-execution.
- **Interrupt during a non-communication turn**: If an action plan is interrupted, then it is not awaiting a reply and the record must not claim it is, because recovery for a hard-killed action turn is `_marked_interrupted_plan`'s job and a false record would divert it into the reply path.
- **Immediate-exit contract**: If the interrupt's exit path forbids I/O, then the record cannot be written after the signal fires; the state is written before the turn's output exists and cleared at finalization, so the guarantee does not depend on a code path that must run instantly.
- **Legacy sessions**: If a session was written before this slice, then it carries no record; a one-time derivation from the last turn's shape persists the record with a logged note, so the inference survives exactly once and never as a standing fallback.
- **Reply supplied but not awaiting**: If the user resumes with `-m` on a session that is not awaiting, then the message is an ordinary next instruction and is not consumed as a reply, which the record now makes decidable.
- **Empty message**: If `resume -m ""` is passed, then the prompt is offered only when presence allows it, per the presence-versus-approval distinction in the ubiquitous language, and the state machine must not treat an empty message as a reply.
- **Pipeline resume**: If a pipeline run resumes, then no prompt is offered and the recorded state still governs which branch executes, because presence gates prompting and never state.
- **Double record**: If both the orchestrator and the lifecycle manager can write the state, then only one of them does, because two writers of one meaning is the original defect in a new place.
- **Delivered behaviour is pinned, not re-opened**: If the pending-reply branch is rewritten, then its existing cases must pass unchanged apart from the fence update 06-07 requires, because a slice that quietly changes delivered behaviour is worse than one that leaves a defect open.

## Key Unknowns
- [ ] [Technical] Whether the state can be recorded without putting metadata I/O on the interrupt's immediate-exit path. Design Sensitivity: if a write at the point the plan is known plus a clear at finalization is acceptable → the record exists for the whole turn, both stop paths and a hard kill are covered by one mechanism, the interrupt path performs zero I/O, the pipeline-specific stamp at `:365-368` collapses into it, and the resume tree loses its inference with no new adapter surface; if a pre-execution record is unacceptable because it marks a turn awaiting a reply while it is still running → the write stays at stop time inside the orchestrator's boundary, the interrupt arm gains one guarded write, and the slice must then state that the immediate-exit contract tolerates it.

## Impact
1. `[NEW]` `ISessionManager.mark_awaiting_reply(turn_dir)` and `ISessionManager.clear_awaiting_reply(turn_dir)` — one call each, so no caller performs a load-modify-save in an interrupt-sensitive path, and both are idempotent.
2. `[MIGRATE]` `SessionOrchestrator.execute` — records the state once the plan is known to be a communication turn and clears it at finalization; the pipeline-stop stamp at `:365-368` collapses into that single mechanism.
3. `[MIGRATE]` `SessionLifecycleManager._should_consume_awaiting_reply` — reads the recorded state alone, with the one-time legacy derivation and its logged note.
4. `[PRUNE]` The plan-shape disjunct at `session_lifecycle_manager.py:321`, and nothing else: the other five `is_communication_turn` sites are render, pipeline-stop, and recovery decisions.
5. `[MIGRATE]` `SessionService` — implements the two primitives over the existing turn-meta persistence.
6. `[NEW]` Tests driving both stop paths, the legacy derivation, a hard-killed communicating turn, and the preserved pending-reply behaviour.
7. `[MIGRATE]` The three component pages above — record which component decides when versus what, that plan shape is no longer a resume input, and the two new session-contract primitives.
8. `[NEW]` `docs/architecture/core/services/session_lifecycle_manager.md` — the service is 824 lines and carries the whole resume state machine, yet no page exists, so the component map's link to it resolves to nothing.

## Deliverables
- [ ] **Interface** — Add the two state primitives to the session contract, documenting that recording is idempotent and clearing is a no-op when absent, and remove plan shape from the documented resume inputs.
- [ ] **Harness** — Add the both-stop-paths, legacy-derivation, and hard-kill tests, plus the pending-reply regression test that survives the rewrite of the same branch.
- [ ] **Core** — Record when a communication turn is known, clear at finalization, and collapse `_should_consume_awaiting_reply` to the recorded state alone.
- [ ] **Cleanup** — Delete the plan-shape disjunct, record the decision, the legacy note, and the delivered pending-reply rule on the three existing component pages, and author the missing `session_lifecycle_manager.md` so the component map's link resolves.

## Implementation Notes

## Verification
1. **Both paths agree:**
   Interrupt a communicating turn and pipeline-stop another, then inspect each turn's `meta.yaml`.
   Verify both carry the same record and both resume through the one branch.
2. **No plan-shape signal:**
   Run `git grep -n 'is_communication_turn' -- src/teddy_executor/core/services/session_lifecycle_manager.py`.
   Verify only the recovery classifier remains.
3. **Pending reply preserved:**
   Run `uv run pytest tests/suites/unit/core/services/test_session_lifecycle_pending_plan_non_communication_resume.py`.
   Verify every case passes after the fence update, with no case deleted.
4. **Legacy session:**
   Resume a session written before the change.
   Verify the derived record is persisted with a logged note and behaviour matches the pre-change run exactly once.
