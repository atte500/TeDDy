# Slice: Write the Execution-Started Marker Before Dispatch
- **Status:** In Progress
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** None
- **Specs:** N/A
- **Prototype:** [04-finalize-as-interrupted-recovery-proof.py](/spikes/debug/resume-after-container-kill/04-finalize-as-interrupted-recovery-proof.py)
- **Component Docs:** [execution_orchestrator.md](/docs/architecture/core/services/execution_orchestrator.md), [session_manager.md](/docs/architecture/core/ports/outbound/session_manager.md)
- **Scope Slug:** `execution-marker`

## Goal
Persist durable evidence that a session turn began executing, so a later `resume` can distinguish a mid-execution kill from a never-dispatched turn. The orchestrator writes an empty `execution.started` marker into the turn directory immediately before the first dispatch, only for session plans.

## Context
- `ExecutionOrchestrator.execute` resolves the plan, validates it, performs interactive review, returns an aborted report when review yields `None`, then calls `_process_plan_actions` and assembles the report.
- `ExecutionOrchestrator.__init__` binds `self._file_system_manager`; `IFileSystemManager.write_file(path, content)` creates or overwrites a file.
- `Plan.is_session` is derived from `.teddy/sessions/` in the plan path, and a session plan always carries `plan_path`.
- `TextualPlanReviewer` returns the same `Plan` instance it received (no `Plan(` construction under `adapters/inbound/`), so `is_session`/`plan_path` survive review.
- `SessionService.get_session_state` classifies a turn from `plan.md`/`report.md` presence only; nothing records that execution began.
- `transition_to_next_turn` copies no files into the next turn, so the marker cannot leak forward.
- Cross-platform path assertions compare through `mocking.to_posix_path`; the marker is written as a root-relative POSIX path.

## Scenarios
> As a developer resuming after a hard kill, I want the session to record that a turn began executing, so resume can recover it instead of replaying already-applied actions.

```gherkin
Given a session plan passes pre-flight validation and plan review
When the orchestrator begins dispatching its actions
Then an empty execution.started marker exists in the turn directory
```

## Edge Cases
- **Non-session plan**: If `reviewed_plan.is_session` is False (stateless `--plan-content` execution), then no marker is written, because only session turns need recovery and stateless runs must leave no turn residue.
- **Pre-flight rejection**: If plan validation fails, then `InvalidPlanError` raises before the marker write, so no marker exists and resume keeps today's replan path.
- **Aborted review**: If the reviewer returns `None`, then the aborted report returns before the marker write, so an aborted turn carries no marker.
- **Communication turn**: If a session plan is a MESSAGE-only turn, then the marker is still written before dispatch, because the marker records execution start, not action type; the resume gate excludes communication turns from recovery.
- **Re-execution**: If a pending turn runs again without recovery, then the same empty marker is overwritten harmlessly.

## Key Unknowns
None. The insertion point, guard, and path derivation are established by inspection; MRE-04 proves the recovery chain that consumes the marker.

## Impact
1. `[NEW]` `EXECUTION_STARTED_MARKER` constant in `core/ports/outbound/session_manager.py` — single-sources the `execution.started` filename for the writer, the reader, and tests.
2. `[EXTEND]` `ExecutionOrchestrator.execute` — write the marker after the review-abort branch and before `_process_plan_actions`, guarded on `reviewed_plan.is_session`.
3. `[MIGRATE]` none — no existing caller changes.
4. `[PRUNE]` none.

## Deliverables
- [x] **Interface** - Add `EXECUTION_STARTED_MARKER` to `core/ports/outbound/session_manager.py` and pin its value in a unit test.
- [x] **Core** - Write the marker in `ExecutionOrchestrator.execute` after the review-abort branch and before `_process_plan_actions`, guarded on `reviewed_plan.is_session`. Unit tests cover: session plan writes the marker before the first dispatch; non-session plan writes none; aborted review writes none; pre-flight rejection writes none.

## Implementation Notes
- **Interface (single-source the marker filename):** `EXECUTION_STARTED_MARKER = "execution.started"` lives in `core/ports/outbound/session_manager.py` beside `SessionState`, so the writer, the resume gate, and the tests share one literal instead of repeating the string. Pinned by `tests/suites/unit/core/ports/test_execution_started_marker.py`, which imports the public port module rather than a private symbol. The constant is behavior-neutral today because no production code reads it; the marker is first written by the pending Core deliverable.
- **Core (marker write before dispatch):** `ExecutionOrchestrator._write_execution_started_marker` writes an empty `{turn_dir}/execution.started` through the already-injected `IFileSystemManager`; `execute` calls it after the review-abort branch and before `_process_plan_actions`, guarded on `reviewed_plan.is_session`. The path derives from `plan.plan_path or plan_path` and is built as `Path(marker_source).parent / EXECUTION_STARTED_MARKER` then `.as_posix()`, so it stays root-relative and POSIX on every platform, and the contract assert names the missing precondition instead of silently skipping the write. The first Green attempt raised `NameError` because the helper used module-scope `os`, which only `execute` imported locally; the fix imports `Path` and the shared constant instead, removing the `os` dependency from the helper entirely. Driven by `tests/suites/unit/core/services/test_execution_orchestrator_execution_marker.py`, which records filesystem writes and dispatches into one ordered event list so the ordering claim is explicit (marker write at index 0, strictly before the first dispatch), and covers the three absence paths: non-session plan, aborted review, and pre-flight rejection.
- **Re-partition deviation:** this slice ships the writer only; the marker reader (the `resume` gate plus both recovery helpers) lands in 00-24, and the two pending-plan suites are pinned path-keyed in 00-23. Splitting them keeps every commit behavior-preserving: the writer with no reader changes nothing observable, the pins change only test doubles, and the gate then arrives against already-pinned suites instead of flipping them at the same commit.

## Verification
1. **Marker written for a session turn:**
   Run a session turn that executes at least one action, then open `.teddy/sessions/<session>/<turn>/` and confirm `execution.started` exists beside `plan.md` and `report.md`.
2. **No marker on an aborted review:**
   Start a session, cancel the plan reviewer, then open `.teddy/sessions/<session>/<turn>/` and confirm no `execution.started` exists.
3. **No marker for stateless execution:**
   Run `teddy execute` on a plan that creates a new file, then confirm no `execution.started` appears anywhere under `.teddy/sessions/`.
