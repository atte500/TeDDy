# Slice: Delete the Discarded Replan Correction Directive
- **Status:** Planned
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** None
- **Specs:** N/A
- **Prototype:** [03-replan-deletion-equivalence-mre.py](/spikes/debug/replan-feedback-visibility/03-replan-deletion-equivalence-mre.py)
- **Component Docs:** [session_orchestrator.md](/docs/architecture/core/services/session_orchestrator.md)
- **Scope Slug:** `replan-directive`

## Goal
Remove the replan correction directive that no write path delivers, so `SessionReplanner` carries only the behavior the system observes, and pin the resulting delegation contract so the discarded directive cannot return unnoticed.

## Context
Findings from the Case File 80 investigation and the preserved MREs.

- `SessionReplanner._build_feedback_message` (`src/teddy_executor/core/services/session_replanner.py:65`) builds the wrapper sentence, the validation errors, an optional AST block, and the faulty plan in a fenced block. `trigger_replan_turn` is its only consumer.
- `PlanningService.generate_plan` skips `meta["user_request"]` on a replan turn, never appends `resolved_message` to `messages`, and writes only `full_context` to `input.md`. Since `d010a1c5` collapsed the planning request to context-only, the directive has no carrier. MRE 01 observed the request as `['system', 'user']` with no directive text.
- The failure evidence the model needs already arrives: `transition_to_next_turn` puts the failed turn's `plan.md` and `report.md` into the replan turn's `turn.context`, and `ContextService._format_content` embeds them verbatim. MRE 02 verified all four content checks.
- MRE 03 compared the production replanner against `replica_session_replanner.py`, which omits the directive, and observed identical requests, file writes, and turn metadata.
- `trigger_replan_turn` has exactly one production caller, `session_lifecycle_manager.py:640`. Spikes also call it but are excluded from all quality gates. A single caller means the signature reduction and the caller update must land in the same commit.
- `tests/suites/unit/core/services/test_session_lifecycle_manager.py:34` builds the replanner with `register_mock(container, SessionReplanner)`, so the double enforces the real signature: reducing the callee without updating the caller raises `TypeError` at the four `trigger_replan` tests.
- Those four tests assert `build_failure_report` and `transition_to_next_turn` arguments, not `trigger_replan_turn`, so they stay green once the caller is updated.
- `trigger_replan` keeps its own `errors`, `original_plan_content`, and `validation_ast` parameters because `build_failure_report` consumes them; only the `trigger_replan_turn` call loses three arguments.
- MRE 03's `invoke_production` calls the four-argument signature, so the preserved spike must have that one call updated to the reduced shape before it can be re-run against the shipped code. MREs 01 and 02 stay untouched as pre-change evidence.
- `build_failure_report`, `gather_failed_resources`, the container wiring at `container.py:332`, and every human-reply path are out of scope.
- No component design doc exists for `SessionReplanner` or `SessionLifecycleManager`. `docs/architecture/core/services/session_orchestrator.md:21` describes `build_failure_report` and stays accurate.

## Scenarios

> As a developer whose plan failed structural validation, I want the automated replan turn to ask for a corrected plan from the carried failure evidence, so that the loop keeps recovering without a directive the request never carried.

```gherkin
Given a session turn whose plan fails structural validation
When the automated replan loop fires
Then the replan turn asks the planning service for a new plan in the next turn directory
And it passes no separate user message, because the failed turn's report and plan already carry the correction context
```

```gherkin
Given a replan turn is requested with a target turn directory
When the planning service generates the plan
Then the planning request carries only the system prompt and the assembled project context
And no validation-errors directive appears in it
```

## Edge Cases
- **Single production caller**: If the callee signature changes, then the caller and the test must change in the same commit, because `register_mock` auto-specs the class and rejects either half.
- **Half-change on the callee**: If `trigger_replan_turn` shrinks while `session_lifecycle_manager.py:640` still passes four arguments, then the four `trigger_replan` tests fail with `TypeError`, because the autospec double enforces the real signature.
- **Half-change on the caller**: If the caller drops three arguments while the callee still requires them, then the same four tests fail with `TypeError`, because the third positional argument is required.
- **Empty turn directory**: If `next_turn_dir` is empty, then it reaches `generate_plan` unchanged; the method adds no validation of its own, because turn-path resolution belongs to the session service.
- **Multiple validation errors**: If a failure carries several errors, then they are no longer joined into a directive; the failure report's `## Validation Recovery` section is the instruction the model reads.
- **Original plan content**: If the model needs the faulty plan, then it reads it from the failed turn's `plan.md` in `turn.context`, not from a removed argument.
- **Validation AST**: If an AST view was attached, then it still lands on the failure report, because `build_failure_report` keeps its `validation_ast` parameter untouched.
- **Preserved MRE**: If MRE 03 is re-run after the deletion, then both sides call `trigger_replan_turn` with a single turn directory and still report identical requests, writes, and metadata.
- **Human reply path**: If a turn carries an awaiting reply, then nothing changes, because the directive never touched that path.

## Key Unknowns

None. Case File 80 resolved every unknown: MRE 01 pinned the directive's absence from the request, MRE 02 pinned the failure evidence's presence, and MRE 03 pinned the deletion as behavior-preserving.

## Impact

1. [MIGRATE] `src/teddy_executor/core/services/session_replanner.py` — delete `_build_feedback_message` and reduce `trigger_replan_turn` to `next_turn_dir`, forwarding `generate_plan(user_message=None, turn_dir=next_turn_dir)`.
2. [MIGRATE] `src/teddy_executor/core/services/session_lifecycle_manager.py` — drop `errors`, `original_plan_content`, and `validation_ast` from the `trigger_replan_turn` call at line 640.
3. [EXTEND] `tests/suites/unit/core/services/test_session_replanner.py` — add one regression test pinning the forwarded planning call, backed by a recording planning-service fake.
4. [MIGRATE] `spikes/debug/replan-feedback-visibility/03-replan-deletion-equivalence-mre.py` — update `invoke_production` to the reduced signature so the preserved MRE runs against the shipped API.
5. [DOC] `docs/project/debugging/80-discarded-replan-feedback.md` — set Status to Resolved and record the outcome.

## Deliverables

- [ ] **Core** - Pin the replan delegation contract and remove the discarded directive: add one regression test proving `trigger_replan_turn(dir)` forwards `user_message=None, turn_dir=dir`, delete `_build_feedback_message`, reduce `trigger_replan_turn` to `next_turn_dir`, drop the three dead arguments at `session_lifecycle_manager.py:640`, and update the preserved MRE's production invocation so the equivalence harness runs against the shipped signature.

## Implementation Notes
Pending implementation.

## Verification

1. **Preserved MRE:**
   Run `uv run python spikes/debug/replan-feedback-visibility/03-replan-deletion-equivalence-mre.py`.
   Verify the output ends with `MRE PASS: deleting the feedback builder is behavior-preserving.`, reports `requests identical: True`, `file writes identical: True`, `turn metadata identical: True`, and prints `feedback text in production request: False`.

2. **Directive removed:**
   Run `git grep -n "_build_feedback_message" -- src tests`.
   Verify no output and exit code `1`.

3. **Contract pin:**
   Open `tests/suites/unit/core/services/test_session_replanner.py`.
   Verify exactly one case drives `SessionReplanner(SessionReplanner(...)).trigger_replan_turn("session/02")` through a recording planning service and asserts the single recorded call carries `user_message=None` and `turn_dir="session/02"`.

4. **Live replan:**
   Start a session and let a turn reply with a structurally invalid plan, for example two Level 1 headings.
   Confirm the console prints `Validation failed... replanning`, the next turn directory is created, and its `input.md` embeds the failed turn's `plan.md` and `report.md`.
