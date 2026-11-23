# Slice: Recover a Marked Interrupted Turn on Resume
- **Status:** In Progress
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** [00-23-pending-plan-path-pins.md](/docs/project/slices/00-23-pending-plan-path-pins.md)
- **Specs:** N/A
- **Prototype:** [04-finalize-as-interrupted-recovery-proof.py](/spikes/debug/resume-after-container-kill/04-finalize-as-interrupted-recovery-proof.py)
- **Component Docs:** None — `SessionLifecycleManager` has no component document; adding it is tracked in Milestone 6.
- **Scope Slug:** `interrupted-turn-recovery`

## Goal
On `resume`, recover a `PENDING_PLAN` session turn that carries the `execution.started` marker instead of replaying its abandoned plan into a pre-flight rejection. The interrupted turn is finalized with an INTERRUPTED report, its reply is carried as `## User Request`, and the next turn is planned from scratch against the observed workspace.

## Context
- `resume`'s `PENDING_PLAN` branch: the awaiting-reply consume returns at `session_lifecycle_manager.py:99-110`; seed-and-dispatch runs at `:111-127`.
- `_parse_pending_plan` returns `None` on bare resume; `_parse_awaiting_plan(turn_path, plan_path=...)` parses with path precision and raises `InvalidPlanError` when unparseable.
- `_synthesize_message_report` shows the assemble shape: `self._time_service.now_utc()` plus `self._report_assembler.assemble(ReportAssemblyData(...))`.
- `ExecutionReportAssembler` folds `ActionStatus.INTERRUPTED` into `RunStatus.INTERRUPTED`, sets `user_request` from `message`, and `execution_report.md.j2:322-325` renders `## User Request`; `_is_preserved_turn` promotes a turn into prune-exempt `session.context` on that heading.
- `finalize_turn(plan_path, report, plan=plan)` writes `report.md` and returns the successor turn directory.
- `_handle_planning_and_execution(turn_dir, orchestrator, require_approval, project_context=, pipeline=, message=)` triggers planning, then executes the new plan.
- `_consume_awaiting_reply` already ends with `finalize_turn` then `_handle_planning_and_execution(message=reply)`; the recovery mirrors that tail.
- The gate classifies a bare-resume marker with a local plan so the existing seed-and-dispatch routing stays byte-identical when recovery does not fire.

## Scenarios
> As a user whose container was killed mid-turn, I want `teddy resume` to record the interrupted turn and continue with a fresh plan, so I do not need `-m` guidance or manual `.teddy/` surgery.

```gherkin
Given a session turn has plan.md, no report.md, and execution.started
When the user runs teddy resume with no message
Then the turn is finalized with an INTERRUPTED report
And the next turn is planned from scratch against the observed workspace
```

```gherkin
Given a session turn has plan.md, no report.md, and execution.started
When the user runs teddy resume -m "next instruction"
Then the reply is recorded as the interrupted report's User Request
And the next turn is planned with that reply
```

## Edge Cases
- **Marker absent**: If the turn carries no marker, then today's seed-and-dispatch runs unchanged, so a never-dispatched turn keeps Bug 60's in-place `-m` completion.
- **Marked communication turn**: If the pending plan is a pure MESSAGE turn, then it is not recovered; the existing re-dispatch path runs so the message re-collects the reply.
- **Marked unparseable plan**: If parsing the marked plan raises `InvalidPlanError`, then the gate falls through to today's `execute -> InvalidPlanError -> trigger_replan` path; the error is not swallowed.
- **Empty reply**: If an interactive blank-message prompt returns an empty reply, then the session terminates before the gate.
- **Awaiting-reply flag**: If the turn is flagged `awaiting_reply`, then the awaiting-reply consume runs before the gate.
- **Blank-message prompt produced a reply**: If the prompt yields a reply that parses to a communication plan, then the awaiting-reply consume runs before the gate.
- **Reply passthrough**: If a reply is injected, then it reaches the synthesized report as `## User Request` and seeds the next turn's planning.
- **No replay**: If recovery fires, then the abandoned plan is never handed to `orchestrator.execute`; only the successor turn's plan is executed.
- **Preservation**: If a reply is present, then `finalize_turn` promotes the interrupted turn's `plan.md` and `report.md` into prune-exempt `session.context`; without a reply, the turn follows normal action-turn behavior.

## Key Unknowns
None. MRE-04 proves the synthesize, finalize, preserve, and next-turn-plan chain with a reply; the bare-resume branch reuses the same helpers with `message=None`.

## Impact
1. `[NEW]` `SessionLifecycleManager._synthesize_interrupted_report` — build the INTERRUPTED report from the pending plan and an outcome-not-recorded note.
2. `[NEW]` `SessionLifecycleManager._recover_interrupted_turn` — finalize the interrupted turn, then plan the successor.
3. `[EXTEND]` `SessionLifecycleManager.resume` — insert the marker gate between the awaiting-reply consume and the seed-and-dispatch.
4. `[MIGRATE]` pending-plan unit suites — add marker-present coverage for recovery, communication re-dispatch, and the unparseable fallback.
5. `[PRUNE]` none.

## Deliverables
- [▶] **Core** - Implement `_synthesize_interrupted_report` and `_recover_interrupted_turn`, then wire the marker gate in `resume` using a local classification plan. Drive it with resume-level unit tests: marker present plus non-communication recovers (INTERRUPTED report, abandoned plan not re-executed, next-turn planning); marker present plus communication keeps re-dispatch; marker present plus unparseable falls through; marker absent stays unchanged.

## Implementation Notes
The existing acceptance test `tests/suites/acceptance/test_pipeline_message_and_resume_flow.py:384-419` remains the end-to-end regression guard for the marker-absent path (Bug 60 in-place completion). The gate itself is unit-tested at the service boundary because constructing a killed workspace end-to-end would require a fake LLM and a real subprocess kill; MRE-04 covers the runtime chain.

## Verification
1. **Recover a simulated kill:**
   In a scratch repo, create a pending turn, then run `touch .teddy/sessions/<session>/<turn>/execution.started` and `teddy resume`.
   Verify the turn gains a `report.md` whose overall status is `INTERRUPTED` and a new turn directory is created.
2. **Reply handoff:**
   Repeat with `teddy resume -m "continue"`.
   Verify the interrupted `report.md` contains a `## User Request` block with `continue` and the next plan is seeded with it.
3. **Never-dispatched turn unchanged:**
   Arrange a `PENDING_PLAN` turn without `execution.started` and run `teddy resume -m "..."`.
   Verify the pending plan runs in place, as Bug 60 requires.
4. **One-line marker inspection:**
   Confirm `git grep -n "execution.started" -- src tests` shows the constant used by the writer, the reader, and both suites.
