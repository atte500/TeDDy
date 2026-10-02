# Bug: `resume -p` Consumption Defects — Stop-Again Display Divergence & Finalization Content Misrouting

- **Status:** Resolved
- **Milestone:** N/A (ad-hoc slice)
- **Vertical Slice:** [00-21-session-interrupt-resume-message.md](/docs/project/slices/00-21-session-interrupt-resume-message.md)
- **Specs:** [report-format.md](/docs/project/specs/report-format.md)

## Symptoms

Two defects surfaced during the manual verification of the `session-interrupt-resume-message` slice, both on the `teddy resume -p` consumption path for an interrupted pipeline MESSAGE turn (`plan.md` present, no `report.md`, `meta.yaml` `awaiting_reply: true`).

### 4a — Stop-again display diverges from the normal pipeline display

**Steps:**
1. `uv run teddy start -a assistant -p -m "Say hi and ask how I am"` — the pipeline turn stops; `01/` holds no `report.md`, `meta.yaml` has `awaiting_reply: true`.
2. `uv run teddy resume -p` (no message — the "Case 2: stop-again" path).

**Expected:** the agent's MESSAGE is re-printed exactly as on the initial pipeline stop — the `🟢 {plan title}` status header line, then a CYAN `--- MESSAGE from TeDDy ---` header, then the message body.

**Actual:** only a bare block is printed:
```
--- MESSAGE from TeDDy ---
Hi there! ...
```
There is no `🟢 {title}` status header and the header line is NOT cyan (the plain rich `Console(stderr=True).print` path).

The user also asked (DRY) that the MESSAGE framing/printing be unified into a single shared code path, because the literal `--- MESSAGE from TeDDy ---` is currently duplicated across three production sites.

### 4b — The agent's own message is misrepresented as the user's reply, and the injected reply is not reflected

**Steps:**
1. `uv run teddy resume -p -m "I am great, tell me a joke"` on the awaiting-reply session.

**Expected:** turn 01 is finalized (standard message-turn report) and the session continues from the injected reply; the report must not misrepresent the agent's message as the user's reply, and the next turn must act on the injected reply.

**Actual:** turn 01's `report.md` renders the AGENT's greeting under `- **User Reply:**`:
```
### `MESSAGE`: [](/)
- **Status:** SUCCESS
- **User Reply:**
```
Hi there! 👋
I'm the **Assistant** — ...
```
```
And turn 02 re-asked the greeting ("how are you doing today?") instead of acting on the injected reply.

## Context & Scope

### Regressing Delta
Introduced by the consumption-semantics amendment of the `session-interrupt-resume-message` slice:
- `03b72ae7` — reply-driven finalization (`_consume_awaiting_reply` + `_synthesize_message_report`).
- `01d475ff` — pipeline stop-again branch (inline MESSAGE re-print).
- `0e607708` — consumption seam (`SessionPorts.plan_parser` / `time_service` injection).

Before the amendment, `_consume_awaiting_reply` skipped finalization for ALL resume modes on an awaiting-reply turn (no `report.md`); the amendment added the report synthesis and the stop-again inline print, which are the two sites at fault.

### Environmental Triggers
Pipeline mode (`-p`) resume on an awaiting-reply turn. `4a` is reproducible in-process (display-path selection); `4b` requires the full LLM-driven turn-02 planning to observe the "agent doesn't pick it up" consequence.

### Ruled Out
- The pipeline-start MESSAGE suppression (`SessionOrchestrator._is_pipeline_message_stop` + `awaiting_reply` persistence) — behaves as designed and is unit-tested.
- The `awaiting_reply` yaml round-trip (`SessionRepository.save_meta` / `load_meta`) — contract-tested green.
- The consumption-seam field wiring (`SessionPorts.plan_parser` / `time_service`) — unit-tested green.
- The `## User Request` append path is NOT involved (locked design: turn-01 finalization does NOT append a User Request).
- The CLI pipeline-break detection (`session_cli_handlers.py:332-339`) — breaks on the presence/type of a MESSAGE action log, NOT on its `details`; the stop-again report's `details` is not load-bearing.
- The reply threading through planning (`_handle_planning_and_execution(..., message=reply)` → `trigger_new_plan(..., message=message)`) — present and correct; the K2 re-greet is a downstream consequence of the 4b report misrouting.

## Diagnostic Analysis

### Causal Model
- **4a:** `SessionLifecycleManager._consume_awaiting_reply`'s pipeline no-message branch prints via `self._user_interactor.display_message(f"--- MESSAGE from TeDDy ---\n{content}")`. `ConsoleInteractorAdapter.display_message` is a plain `self._console.print(message)` (rich Console, no style) — it neither emits the `🟢 {title}` status header (that is `SessionOrchestrator._print_header_bar`) nor applies CYAN. The normal pipeline path (`SessionOrchestrator.execute`) instead uses `_print_header_bar(plan, is_session)` then `typer.secho("--- MESSAGE from TeDDy ---", fg=typer.colors.CYAN)` + `typer.secho(content)`. The two paths therefore render the same logical event differently, and the framing literal is duplicated.
- **4b:** `SessionLifecycleManager._synthesize_message_report` builds a single `ActionLog(action_type="MESSAGE", params={"content": content}, details=content)` where `content` is the AGENT's message. The template's `render_action_details` macro renders a MESSAGE log's `details` under `- **User Reply:**`. So the agent's greeting is stored and rendered as the user's reply; the injected reply "I am great, tell me a joke" appears nowhere in turn 01's report.
  - **Canonical `details` semantics (resolved at source):** a MESSAGE ActionLog's `details` slot canonically holds the USER's reply, with the AGENT's own text in `params["content"]`. Confirmed by three independent production artifacts: `action_executor.py:205-207` ("For MESSAGE actions, return the user's typed message from action_log.details"), the Bug-16 regression test (`test_bug_16_message_user_request.py`: "MESSAGE action replies belong exclusively in action_log.details"), and `test_report_message_fencing.py` (asserts a string `details` renders under `**User Reply:**`). The finalization synthesis is the odd one out. Proven fix: `_synthesize_message_report` must store the injected USER `reply` in `details` (agent text stays in `params["content"]`).
  - **Pipeline vs interactive semantics:** the ephemeral pipeline short-circuit (`action_executor.confirm_and_dispatch` pipeline branch) and the pipeline MESSAGE print (`session_orchestrator.py:341`) set/read `details` as the AGENT message. Because a pipeline MESSAGE turn stops before finalization, that pipeline report is NEVER persisted; this is a pre-existing, presentation-only inconsistency that does not reach `report.md`. The persisted report comes solely from the synthesis.
  - **4b → turn-02 starvation (K2):** `PlanningService.generate_plan` stores the threaded `message` ONLY into `meta["user_request"]`, never into the LLM `messages` (`full_context` = gathered file context). `session_service.py:296` confirms the next turn's context always includes the prior turn's `plan.md` + `report.md`. Therefore the reply reaches turn 02 ONLY through turn-01's report `- **User Reply:**` field, which currently carries the agent's message → the LLM never learns the real reply and re-greets. Fixing the synthesis to write `details=reply` resolves K2 as a byproduct.

### Discrepancies
- The locked finalization design (user, turn 13) described turn-01's finalized `report.md` as the "standard message-turn shape". The turn-15 evidence shows that populating the MESSAGE log's `details` with the AGENT's message produces a semantically wrong `- **User Reply:**` block. (Resolved: the standard message-turn shape carries the USER's reply in `details`, with the agent text in `params["content"]`; see Causal Model 4b. The synthesis's `details=content` is the defect.)
- `_handle_planning_and_execution(..., message=reply)` DOES thread the reply into `trigger_new_plan(turn_dir, message=message)`, yet turn 02 did not act on it. (Resolved at source: the reply reaches turn 02 only via turn-01's report `User Reply` field, which the synthesis fills with the agent's message; `generate_plan` puts the reply only in `meta["user_request"]`, not in the LLM `messages`. The synthesis fix resolves this. Empirical end-to-end confirmation deferred to the fix's acceptance test.)

### Investigation History
1. Hypothesis: the stop-again path uses a different display path than normal execution. Observation: `git grep "--- MESSAGE from"` returned three sites — `console_interactor.py:78` (ask-flow, cyan), `session_orchestrator.py:341` (pipeline print, cyan, preceded by `_print_header_bar`), `session_lifecycle_manager.py:191` (stop-again inline, no color/header). Conclusion: 4a confirmed — display divergence + duplicated framing literal.
2. Hypothesis: the synthesized report stores the agent's message in the `details` slot. Observation: `_synthesize_message_report` sets `details=content` (agent message); the template renders MESSAGE `details` under `**User Reply:**`. Conclusion: 4b content-misrouting confirmed.
3. Hypothesis: the injected reply is not threaded to turn-02 planning. Observation: the reply IS threaded via `message=reply` → `trigger_new_plan(..., message=message)`. Conclusion: threading present; the "agent doesn't pick it up" symptom likely originates from the mislabeled report in turn-02's context (UNCONFIRMED — build an MRE).
4. Hypothesis: a MESSAGE `details` slot canonically holds the USER's reply. Observation: `action_executor.py:205-207` ("return the user's typed message from action_log.details"), the Bug-16 test, and `test_report_message_fencing.py` all agree. Conclusion: canonical `details` = user reply; `_synthesize_message_report(details=content)` is the 4b defect.
5. Hypothesis: the CLI pipeline break depends on the MESSAGE log's `details`. Observation: `session_cli_handlers.py:332-339` breaks on the presence/type of a MESSAGE action log, not on `details`. Conclusion: the stop-again report's `details` is NOT load-bearing; a `details=reply` fix does not regress the stop-again path.
6. Hypothesis (empirical 4b MRE): driving the REAL `_consume_awaiting_reply` + REAL `MarkdownReportFormatter` reproduces the misrouting. Observation: `spikes/debug/54-resume-p-finalization-mre.py` wrote `01/report.md` rendering the agent's greeting under `- **User Reply:**` with the injected reply absent → AssertionError "defect 4b reproduced". Conclusion: 4b proven at runtime.
7. Hypothesis (zero-touch shadow fix): `_synthesize_message_report(details=reply)` fixes 4b. Observation: `spikes/debug/shadow_session_lifecycle_manager.py` (fix applied) makes the same MRE pass — `- **User Reply:**` now contains "I am great, tell me a joke" and the agent's message is not mislabeled. Conclusion: fix empirically proven without touching `src/`.
8. Hypothesis: the reply reaches turn-02 planning only via turn-01's report. Observation: `PlanningService.generate_plan` stores the threaded message only in `meta["user_request"]` (not in the LLM `messages`); `session_service.py:296` injects the prior turn's `plan.md` + `report.md` into the next turn's context. Conclusion: the misrouted report starves turn 02 of the real reply (K2); the synthesis fix should resolve it.
9. Hypothesis (systemic audit — categorization): both defects share one abstract category. Observation: 4a and 4b each re-implement a MESSAGE event (presentation / report synthesis) instead of reusing the canonical MESSAGE-turn idioms, both introduced by the same consumption amendment. Conclusion: category = "parallel-path divergence"; generalized fix = a single source of truth for MESSAGE rendering consumed by every path.
10. Hypothesis (systemic audit — categorical census): other sites diverge in the same category. Observation: `git grep` found exactly three `--- MESSAGE from ... ---` framing sites (`console_interactor.py:78` ask-flow, `session_orchestrator.py:341` pipeline, `session_lifecycle_manager.py:191` stop-again); `display_message` is a GENERIC channel (planning/telemetry/errors) — carrying MESSAGE framing on it would be semantically wrong. Conclusion: the MESSAGE renderer must be its own interior core seam; no other divergent MESSAGE handler exists.
11. Hypothesis (systemic audit — impact audit + fix home): a shared helper forces a Port/Contract change. Observation: both 4a consumers are core services; `session_orchestrator.py` already imports `typer` in core and `session_lifecycle_manager.py` already imports `_print_initial_request` from `session_orchestrator`; the originating slice 00-21 is In Progress. Conclusion: interior core helper, NO `IUserInteractor` Port change (no Contract/Harness deliverable); append the fix deliverables to slice 00-21.

## Solution
_(RCA proven; 4b fix empirically verified via shadow; 4a DRY fix shape confirmed by the user at the Alignment gate. Fix deliverables are appended to [00-21-session-interrupt-resume-message.md](/docs/project/slices/00-21-session-interrupt-resume-message.md); implementation handed to the Developer.)_

Root cause (single chain): the `resume -p` consumption amendment (`03b72ae7`, `01d475ff`, `0e607708`) introduced two sites that diverge from the established MESSAGE-turn idioms.

- **4a — presentation divergence (stop-again path).** `_consume_awaiting_reply`'s no-message pipeline branch re-prints the agent's MESSAGE via `display_message` (a plain, un-styled rich `Console.print`) with a hardcoded `--- MESSAGE from TeDDy ---` literal. The normal pipeline path instead prints the `🟢 {title}` status header (`_print_header_bar`) then a CYAN `--- MESSAGE from TeDDy ---` via `typer.secho`. The same logical event therefore renders differently, and the framing literal is duplicated 3×.
- **4b — finalization content misrouting.** `_synthesize_message_report` stores the AGENT's message in the MESSAGE ActionLog's `details` slot, which the template renders under `- **User Reply:**`. Canonically (`action_executor.py:205-207`, Bug-16 test, `test_report_message_fencing.py`) `details` holds the USER's reply with the agent text in `params["content"]`. The misrouted `details` also starves turn 02 of the real reply (the reply reaches the next turn only through turn-01's report `User Reply` field), causing the re-greet (K2).

Proven fix (4b, Zero-Touch shadow): thread the injected `reply` into `_synthesize_message_report` and store it in the MESSAGE log's `details` (`details=reply`), keeping the agent's message in `params["content"]`. The MRE flips FAIL→PASS against `spikes/debug/shadow_session_lifecycle_manager.py`.

Confirmed fix (4a, user-approved DRY at the Alignment gate): introduce a single shared MESSAGE-rendering helper — status header + cyan `--- MESSAGE from TeDDy ---` + body — consumed by BOTH the orchestrator's pipeline path and the lifecycle manager's stop-again branch (DRY; also removes the 3×-duplicated framing literal already logged in PROJECT.md Technical Debt). Interior core helper (mirrors the existing `_print_initial_request` import precedent between the two core services); NO `IUserInteractor` Port change, so no Contract/Harness deliverable.

Abstract category: **parallel-path divergence** — the consumption amendment re-implemented a MESSAGE event (presentation 4a; report synthesis 4b) instead of reusing the canonical MESSAGE-turn idiom, so the two paths drifted and the framing literal triplicated.

Systemic preventative: a single MESSAGE-framing constant/helper plus a regression test asserting the two display paths are byte-identical; and a regression test asserting a finalized message-turn report renders the USER's reply (never the agent's message) under `- **User Reply:**`.
