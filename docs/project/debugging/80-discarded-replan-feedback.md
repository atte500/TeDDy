# Bug: Discarded Replan Correction Directive
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [00-21: Delete the Discarded Replan Correction Directive](/docs/project/slices/00-21-remove-discarded-replan-directive.md)
- **Specs:** N/A

## Symptoms
On an automated replan, the model is expected to receive the focused correction directive that `SessionReplanner` builds: "The previous plan failed validation…", the validation errors, the AST view, and the original faulty plan. It does not. The replan request reaches the LLM as `[system, user(full_context)]`; the directive is computed and discarded.

Reproduction scenario:

1. A session turn produces a structurally invalid plan (for example, two Level 1 headings).
2. `_prepare_plan_parsing` fails; `trigger_replan` builds the failure report, finalizes the turn, and calls `SessionReplanner.trigger_replan_turn`.
3. `trigger_replan_turn` builds the directive via `_build_feedback_message` and passes it as `generate_plan(user_message=...)`.
4. `PlanningService.generate_plan` resolves the directive, then drops it: it is not appended to `messages`, not stored in `meta["user_request"]` because the turn carries `is_replan: true`, and not written to `input.md`.
5. The model still sees the failed turn's `report.md` (validation errors, AST, `## Validation Recovery`) and `plan.md` (the faulty plan) because both are embedded in `full_context`.

The lost piece is the explicit wrapper directive, not the failure evidence. The user-visible impact is model-dependent: the model can infer the correction task from `## Validation Recovery`, but the intended last-position instruction is never delivered.

## Context & Scope
### Regressing Delta
Commit `d010a1c5031fa50f249ccfc91858c5ce38233691` (`fix(core): resolve session loop breakage and restore system stability`, 2026-05-15) replaced the single user message `Context:\n{full_context}\n\nUser Message: {resolved_message}` with a context-only message in the message-assembly block of `src/teddy_executor/core/services/planning_service.py` (lines ~83-91). On a replan turn `resolved_message` is the `SessionReplanner` directive, so that commit severed its only carrier. It did not remove the producer: `SessionReplanner._build_feedback_message` (`src/teddy_executor/core/services/session_replanner.py:65`) still builds the string on every structural failure and still passes it to `generate_plan`. The producer was introduced in `4eaeb54e` and reshaped in `f4bc0699`; the directive was functional until `d010a1c5`.

### Environmental Triggers
Session-mode structural or validation failures that enter `trigger_replan`: `session_orchestrator.py:554` (plan file missing), `:582` (parse exception), and `:665` (validation failure). The omission is deterministic in the request; the model's reaction is provider- and model-dependent.

### Ruled Out
- **Failure evidence missing from the request.** The failed turn's `plan.md` and `report.md` are added to the replan turn's `turn.context` by `transition_to_next_turn`'s non-preserved branch and embedded verbatim by `ContextService._format_content`. Pruning does not run during planning, and heuristic 4 spares the latest validation failure. Proven by MRE 02.
- **The directive being persisted in `report.md`.** `build_failure_report` never receives it and no `write_file` consumes it. Proven by repository-wide grep and MRE 01.
- **Human-reply paths.** Under the shipped default (`preserve_message_turns: true`), approval, `resume -m`, and turn-1 `-m` replies already sit inside `full_context`. They are outside this fix.
- **Wiring or construction changes.** `container.py:332` constructs `SessionReplanner(file_system_manager, planning_service)`; the ports are untouched.

## Diagnostic Analysis
### Causal Model
Verified on the current checkout:

1. `SessionReplanner._build_feedback_message` builds the wrapper sentence, the errors joined by `\n\n---\n\n`, an optional AST block, and `## Original Faulty Plan:` in a twelve-backtick Markdown fence.
2. `trigger_replan_turn` passes that string only as `generate_plan(user_message=feedback, turn_dir=next_turn_dir)`.
3. `PromptManager.resolve_message` returns it unchanged; the `initial_request.md` fallback applies only to turn `01`, and replan turns are `02+`.
4. `PlanningService.generate_plan` skips `meta["user_request"]` when `meta["is_replan"]` is true, never appends `resolved_message` to `messages`, and writes only `full_context` to `input.md`.
5. MRE 01 observed the replan request as `['system', 'user']` with none of the directive text present.
6. The failed turn's `plan.md` and `report.md` are in the replan turn's `turn.context`; MRE 02 observed the validation error, `## Validation Errors:`, `## Validation Recovery`, and the faulty plan all embedded in `full_context`.
7. MRE 03 observed the production replanner and a replica that omits the directive producing identical requests, file writes, and turn metadata, so the directive is unobservable in the request.
8. Before `d010a1c5`, the request embedded `resolved_message` in the single user message, so the directive reached the model until that commit.

### Discrepancies
- [x] The `SessionReplanner` directive never reaches the LLM request. (Resolved: `d010a1c5` removed its carrier and left the producer; verified by MRE 01 and the pre-commit request shape.)
- [x] The failure evidence appeared to be lost together with the directive. (Resolved: the failed turn's `plan.md` and `report.md` ride into the request via `turn.context`; verified by MRE 02.)
- [x] Deleting the producer risked changing observable behavior. (Resolved: MRE 03 shows identical requests, writes, and metadata.)

### Investigation History
1. Inspected `PlanningService.generate_plan` and identified the three write paths for `resolved_message` — `messages`, `meta["user_request"]`, `input.md` — and that the replan turn satisfies none of them.
2. Built `01-replan-feedback-visibility-mre.py` and observed `['system', 'user']` with no validation error, faulty plan, or correction instruction, confirming the directive is absent from the request.
3. Investigated whether the evidence is lost by reading `finalize_turn`, `transition_to_next_turn`, `ContextService._format_content`, and `read_files_in_vault`; observed the failed turn's `plan.md` and `report.md` are listed in the next turn's `turn.context` and embedded verbatim, and that the only `prune(` call site runs after planning.
4. Built `02-replan-context-evidence-mre.py` against a real `LocalFileSystemAdapter` and observed all four content checks true, proving the evidence is already in `full_context`.
5. Traced the directive's history with `git log -S` and `git show d010a1c5^:.../planning_service.py`; observed the pre-commit request carried `User Message: {resolved_message}`, isolating the commit that severed the carrier.
6. Confirmed the directive is never persisted: repository-wide grep shows it only in `session_replanner.py`; `build_failure_report` never receives it.
7. Investigated safe deletion by creating `replica_session_replanner.py` with the producer removed and `trigger_replan_turn` reduced to `next_turn_dir`; built `03-replan-deletion-equivalence-mre.py` and observed identical requests, writes, and metadata.
8. Confirmed the test blast radius: `test_session_replanner.py` covers `build_failure_report` and `gather_failed_resources` only, and the four `trigger_replan` tests in `test_session_lifecycle_manager.py` assert `build_failure_report` and `transition_to_next_turn` arguments, so they remain green under the reduced signature.
9. Confirmed no documentation claims the directive reaches the request; the only reference (`docs/architecture/core/services/session_orchestrator.md:21`) describes `build_failure_report` and stays accurate.

## Solution
### Root Cause
`d010a1c5` collapsed the planning request to context-only and left `SessionReplanner._build_feedback_message` in place, producing a directive that no write path consumes. The failure evidence is not lost; the focused last-position instruction is.

Chosen resolution (user decision: delete): remove `_build_feedback_message`, reduce `trigger_replan_turn` to `next_turn_dir`, and call `generate_plan(user_message=None, turn_dir=next_turn_dir)`. `## Validation Recovery` in the carried failure report remains the instruction.

The deletion was proven behavior-preserving in the sandbox replica `spikes/debug/replan-feedback-visibility/replica_session_replanner.py` by `03-replan-deletion-equivalence-mre.py`: identical requests, file writes, and metadata. The clean change touched two production files, exceeding the Debugger's direct-resolution scope, so implementation was handed off to the Developer as slice [00-21](/docs/project/slices/00-21-remove-discarded-replan-directive.md) and delivered on 2026-11-19: `_build_feedback_message` is deleted, `trigger_replan_turn` takes only `next_turn_dir`, and the call at `session_lifecycle_manager.py:640` passes only that directory. One regression test pins the forwarded planning call as `generate_plan(user_message=None, turn_dir=next_turn_dir)`. Re-run against the shipped signature, MRE 03 still reported identical requests, file writes, and turn metadata with no feedback text in the production request, and `make test` passed 2303 with 5 skipped.

### Affected Components
- `src/teddy_executor/core/services/session_replanner.py`: delete `_build_feedback_message`; reduce `trigger_replan_turn` to `next_turn_dir`, forwarding `user_message=None`. Keep `build_failure_report` and `gather_failed_resources` unchanged.
- `src/teddy_executor/core/services/session_lifecycle_manager.py:640`: drop `errors`, `original_plan_content`, and `validation_ast` from the `trigger_replan_turn` call. `trigger_replan` keeps those parameters because `build_failure_report` consumes them.
- `tests/suites/unit/core/services/test_session_lifecycle_manager.py`: no edit required. The four `trigger_replan` tests assert `build_failure_report`/`transition_to_next_turn` arguments; the auto-specced `SessionReplanner` mock enforces the new signature, so an inconsistent half-change fails here.
- `tests/suites/unit/core/services/test_session_replanner.py`: add one regression test pinning that `trigger_replan_turn(dir)` forwards `user_message=None` and `turn_dir=dir` to the planning service, so a future edit cannot silently reintroduce the discarded directive.
- `spikes/debug/replan-feedback-visibility/`: preserved audit trail — `01-replan-feedback-visibility-mre.py`, `02-replan-context-evidence-mre.py`, `03-replan-deletion-equivalence-mre.py`, and `replica_session_replanner.py`.
- `docs/architecture/core/services/session_orchestrator.md`: no edit required; its description of `SessionReplanner` remains accurate.
- `container.py:332`: no edit; construction ports unchanged.
