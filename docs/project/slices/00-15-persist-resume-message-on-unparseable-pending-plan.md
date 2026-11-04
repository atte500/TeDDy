# Slice: Persist Injected Resume Messages On Unparseable Pending Plans
- **Status:** Planned
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** None
- **Scope Slug:** `resume-message`

## Goal
A user who resumes a `PENDING_PLAN` turn with `-m` keeps their instruction even when that turn's `plan.md` cannot be parsed. The message is written to a durable artifact and its carrying turn is promoted into the prune-exempt session scope, exactly as on the `EMPTY` branch, instead of being silently dropped.

## Context
- `SessionLifecycleManager.resume`: the `PENDING_PLAN` branch parses the pending plan through `_parse_pending_plan` and, when the result is `None`, falls back to `orchestrator.execute(plan_path=...)` with no `message` argument. `_parse_pending_plan` returns `None` both when no message is injected and when `InvalidPlanError` is raised, so an injected string reaches neither `plan.metadata["user_request"]` nor `ExecutionReport.user_request`.
- `SessionOrchestrator._prepare_plan_parsing`: in session mode with a `plan_path`, a parser exception is caught and converted into `SessionLifecycleManager.trigger_replan(..., errors=["Structural error: ..."])`. The fallback therefore does not dead-end: the replan writes a `Validation Failed` report for the resumed turn via `finalize_turn(..., is_validation_failure=True)`, creates the successor turn, and plans it from the structural-error feedback — synchronously, so the resumed turn's `report.md` exists by the time `execute` returns.
- `SessionLifecycleManager._append_message_to_previous_turn`: appends a smart-fenced `## User Request` section to the predecessor turn's `report.md`, then calls `ISessionManager.preserve_turn_in_session_context`. It no-ops when the predecessor report does not exist, which covers turn `01`.
- `SessionService.preserve_turn_in_session_context`: re-evaluates `_is_preserved_turn` (a `^## User Request` heading in `report.md`, or a `^## Message` heading in `plan.md`) and, when `auto_pruning.preserve_message_turns` is enabled, admits `plan.md` and `report.md` to `session.context`.
- `ContextService._collect_items`: keeps one `ContextItem` per path and upgrades a `Turn` entry to a non-`Turn` scope, never the reverse, so promotion survives the duplicate path still listed in the successor's `turn.context`.
- `SessionPruningService`: every heuristic short-circuits on `scope != "Turn"`, including retention, the validation-failure heuristic, and the global budget, so a promoted turn cannot be deselected.
- `SessionLifecycleManager._should_consume_awaiting_reply`: runs before the parse fallback, so an `awaiting_reply` turn is unaffected by this change.
- `SessionReplanner.build_failure_report`: assembles the structural-failure report from `errors`, `title`, and `rationale` only. It carries no user-request field, so neither threading `message=` into the fallback nor depending on the replan can record the injected string.

## Scenarios
> As a user resuming a session, I want my injected instruction recorded even when the pending plan is malformed, so that my instruction is not silently lost.

```gherkin
Given a session whose latest turn has a plan.md that cannot be parsed and no report.md
When I resume with an injected message
Then the resumed turn's report.md records the structural validation failure
And the resumed turn's report.md contains a "## User Request" section with my message
And the resumed turn's plan.md and report.md are listed in session.context
```

## Edge Cases
- **Turn 01 pending plan**: If the unparseable pending turn is `01`, then the section is appended to `01/report.md` and `01` is promoted, because the structural replan writes that report before the lifecycle manager regains control; `initial_request.md` is not touched on this path.
- **Report absent after execution**: If the resumed turn's `report.md` does not exist once `execute` returns, then no append and no promotion occur, because the recording step is guarded on file existence instead of asserting.
- **Preservation disabled**: If `auto_pruning.preserve_message_turns` is false, then the message is still appended to the resumed turn's report but the turn is not promoted, because `preserve_turn_in_session_context` reads the same gate as the `EMPTY` branch.
- **No message injected**: If resume is called without `-m`, then no append and no promotion occur, because the bare re-execute path must stay byte-identical.
- **Awaiting-reply turn**: If the pending turn carries `awaiting_reply`, or its parsed plan is a communication turn, then the reply-consumption path runs first and this change never applies.
- **Parseable pending plan**: If the pending plan parses, then `plan.metadata["user_request"]` is set and the plan is executed by object, because that arm is untouched.

## Key Unknowns
- [ ] [Domain] Replan delivery: Should the injected message also seed the structural replan's feedback so the successor plan acts on it, or is recording-only parity sufficient? Design Sensitivity: if delivery is in scope → `trigger_replan` and `IRunPlanUseCase` gain a message parameter and the slice grows to a second production file; if not → the change stays inside `SessionLifecycleManager` and the message is recorded without shaping the next plan.

## Impact
1. `[EXPAND]` `SessionLifecycleManager.resume` — the `PENDING_PLAN` parse-failure arm gains a post-execute recording step. The `resume` signature and `IRunPlanUseCase.execute` are unchanged, so no caller or contract test is affected.

## Deliverables

- [ ] **Core** - Record an injected message as a `## User Request` section on the resumed turn's structural-failure report after the synchronous replan writes it, then re-run preservation so the turn enters `session.context`.

## Implementation Notes
- Reuse `_append_user_request` and `SessionService.preserve_turn_in_session_context` — the pair the `EMPTY` branch already uses — guarded on the resumed `report.md` existing after `execute` returns.
- Do not reuse `_append_message_to_previous_turn`: it targets turn `M-1`, which would promote an unrelated completed turn into the prune-exempt scope and could resurrect a failure that pruning had already deselected.
- Recording-only parity: the parseable arm sets `plan.metadata["user_request"]` without altering the plan's actions, so this arm records the message without altering the replan. Delivering the message to the replanner is the open `[Domain]` unknown, not part of this slice.
- No change is needed to the successor's `turn.context`: `ContextService._collect_items` deduplicates by path and keeps the promoted `Session` entry over the `Turn` duplicate.
- `SessionLifecycleManager` and the structural-replan arm are not yet listed in the `ARCHITECTURE.md` component map, so this slice links no component doc.

## Verification
1. **Malformed pending plan, mid-session:**
   Take a session whose latest turn has no `report.md` and replace its `plan.md` with a single line of prose, so it carries neither a metadata list nor an `## Action Plan` heading.
   Run `teddy resume -m "keep this instruction"`.
   Verify that turn's `report.md` carries both `- **Overall Status:** Validation Failed` and a `## User Request` section containing `keep this instruction`, and that the session's `session.context` lists that turn's `plan.md` and `report.md`.
2. **Malformed pending plan, first turn:**
   Apply the same `plan.md` edit to turn `01` of a fresh session before its first execution.
   Run `teddy resume -m "keep this instruction"`.
   Verify `01/report.md` carries both `- **Overall Status:** Validation Failed` and the `## User Request` section, and that `session.context` lists `01/plan.md` and `01/report.md`.
