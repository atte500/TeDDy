# Bug: `resume -p` Consumption Defects — Stop-Again Display Divergence & Finalization Content Misrouting

- **Status:** Unresolved
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

## Diagnostic Analysis

### Causal Model
- **4a:** `SessionLifecycleManager._consume_awaiting_reply`'s pipeline no-message branch prints via `self._user_interactor.display_message(f"--- MESSAGE from TeDDy ---\n{content}")`. `ConsoleInteractorAdapter.display_message` is a plain `self._console.print(message)` (rich Console, no style) — it neither emits the `🟢 {title}` status header (that is `SessionOrchestrator._print_header_bar`) nor applies CYAN. The normal pipeline path (`SessionOrchestrator.execute`) instead uses `_print_header_bar(plan, is_session)` then `typer.secho("--- MESSAGE from TeDDy ---", fg=typer.colors.CYAN)` + `typer.secho(content)`. The two paths therefore render the same logical event differently, and the framing literal is duplicated.
- **4b:** `SessionLifecycleManager._synthesize_message_report` builds a single `ActionLog(action_type="MESSAGE", params={"content": content}, details=content)` where `content` is the AGENT's message. The template's `render_action_details` macro renders a MESSAGE log's `details` under `- **User Reply:**`. So the agent's greeting is stored and rendered as the user's reply; the injected reply "I am great, tell me a joke" appears nowhere in turn 01's report, and turn 02 inherits the mislabeled report.

### Discrepancies
- The locked finalization design (user, turn 13) described turn-01's finalized `report.md` as the "standard message-turn shape". The turn-15 evidence shows that populating the MESSAGE log's `details` with the AGENT's message produces a semantically wrong `- **User Reply:**` block. The intended content of `details` on the finalization path is therefore UNRESOLVED (the user's injected reply, the agent's message, or neither?). A design confirmation is required.
- `_handle_planning_and_execution(..., message=reply)` DOES thread the reply into `trigger_new_plan(turn_dir, message=message)`, yet turn 02 did not act on it. Whether the mislabeled turn-01 report content is the cause, or reply consumption in planning is separately broken, is UNCONFIRMED (needs an MRE).

### Investigation History
1. Hypothesis: the stop-again path uses a different display path than normal execution. Observation: `git grep "--- MESSAGE from"` returned three sites — `console_interactor.py:78` (ask-flow, cyan), `session_orchestrator.py:341` (pipeline print, cyan, preceded by `_print_header_bar`), `session_lifecycle_manager.py:191` (stop-again inline, no color/header). Conclusion: 4a confirmed — display divergence + duplicated framing literal.
2. Hypothesis: the synthesized report stores the agent's message in the `details` slot. Observation: `_synthesize_message_report` sets `details=content` (agent message); the template renders MESSAGE `details` under `**User Reply:**`. Conclusion: 4b content-misrouting confirmed.
3. Hypothesis: the injected reply is not threaded to turn-02 planning. Observation: the reply IS threaded via `message=reply` → `trigger_new_plan(..., message=message)`. Conclusion: threading present; the "agent doesn't pick it up" symptom likely originates from the mislabeled report in turn-02's context (UNCONFIRMED — build an MRE).

## Solution
_(To be completed by the Debugger.)_

Root cause: 4a — display-path divergence (the stop-again branch bypasses the orchestrator's status-header + cyan MESSAGE rendering; the framing literal is duplicated 3×). 4b — `_synthesize_message_report` places the agent's message in the MESSAGE ActionLog `details` slot, which the report template renders as the user's reply.

Fix directions (pending a design confirmation for 4b):
- Introduce a single shared MESSAGE-rendering helper (status header + cyan `--- MESSAGE from TeDDy ---` + body) consumed by BOTH the orchestrator's pipeline path and the lifecycle manager's stop-again branch (DRY).
- Correct the synthesized MESSAGE ActionLog so the agent's message is not rendered as the user's reply, and ensure the injected reply is represented and consumed by the next turn.
Preventative: a single MESSAGE-framing constant/helper (already logged in PROJECT.md Technical Debt) plus a regression test asserting the two display paths are byte-identical.
