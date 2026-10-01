# Slice: Session Interrupt, resume -m Message Injection & Pipeline Final-Turn Fix
- **Status:** In Progress
- **Milestone:** [N/A (ad-hoc)](/docs/project/tasks/00-21-session-interrupt-resume-message.md)
- **Specs:** [Task Brief](/docs/project/tasks/00-21-session-interrupt-resume-message.md)
- **Prototype:** [N/A — spike findings recorded in Task Brief]
- **Component Docs:** [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [SessionService](/docs/architecture/core/services/session_service.md), [ShellAdapter](/docs/architecture/adapters/outbound/shell_adapter.md), [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `session-interrupt-resume-message`

## Business Goal
Make TeDDy sessions safely interruptible without losing the audit trail, enable scripted reply injection via `teddy resume -m`, and fix the `-p` pipeline bug where the final MESSAGE turn incorrectly generates `report.md` and initializes a subsequent turn — leaving the session unresumable in a clean state.

## Scenarios

> As a pipeline operator, I want a `-p` session whose turn ends with a MESSAGE action to stop without finalizing the turn so that the session remains resumable in a clean awaiting-reply state.

```gherkin
Given a pipeline session whose executed turn report contains a non-empty MESSAGE action
When the execution orchestrator completes the turn
Then the turn is NOT finalized
And no report.md is written for the turn
And no next turn directory is created
And the turn's meta.yaml contains "awaiting_reply: true"
And the message is printed to the terminal
And the report is returned so the CLI pipeline break fires
```

> As a script author, I want `teddy resume -m "reply"` on an awaiting-reply turn to inject my reply without re-executing the stalled plan so that automation can continue the conversation.

```gherkin
Given a session whose latest turn has plan.md, NO report.md, and "awaiting_reply: true" in meta.yaml
When I run teddy resume -m "reply"
Then the plan is NOT re-executed
And the awaiting_reply flag is cleared
And the next turn is created and planned with the injected reply
And no interactive prompt is shown
```

> As a user, I want `teddy resume -m "new request"` on a fully completed turn to append my request to the report and continue hands-free so that I can script follow-up instructions.

```gherkin
Given a session whose latest turn has both plan.md and report.md
When I run teddy resume -m "new request"
Then a "## User Request" section is appended to the latest report.md
And the message body is wrapped in a smart-fenced codeblock (fence length = longest backtick run + 1)
And the next turn is planned with the injected message without an interactive prompt
And session_service recognizes the turn as a user-request turn
```

> As an interactive user, I want Ctrl+C during plan execution to gracefully drain the in-flight action and preserve the audit trail so that I can stop a session without losing its history.

```gherkin
Given an interactive session executing a multi-action plan containing a long-running EXECUTE
When I press Ctrl+C once
Then the in-flight command is allowed to finish
And all remaining actions are logged as INTERRUPTED with reason "Interrupted by user (Ctrl+C)."
And report.md is generated with the full audit trail
And the process exits normally
When I press Ctrl+C a second time while the command is still running
Then the process is killed immediately
```

> As an interactive user, I want Ctrl+C while the agent is waiting (prompt or LLM planning) to exit immediately so that no partial artifacts are produced.

```gherkin
Given the session is waiting for a user reply via ask_question OR for the LLM planning response
When I press Ctrl+C
Then the process exits immediately
And no report.md or turn transition artifacts are created
```

## Edge Cases
- **Non-pipeline MESSAGE turn**: If the session is NOT in pipeline mode and the turn ends with a MESSAGE, then the turn MUST still be finalized normally (report.md + next turn), in order to preserve the interactive audit trail.
- **Interactive resume of awaiting-reply turn**: If the latest turn is awaiting-reply and no `-m` is provided, then the user is prompted for the reply (mirroring `_handle_aborted_session`), in order to keep the flow usable without scripting.
- **Non-interactive resume of awaiting-reply turn without -m**: If resume is non-interactive with no message, then exit cleanly with guidance, in order to avoid hanging automation.
- **Empty MESSAGE in pipeline**: If the pipeline plan's MESSAGE is empty, then the existing empty-reply termination path (Bug 15) remains authoritative, in order to avoid double-handling.
- **Smart-fence escalation**: If the injected message contains backtick runs (e.g., nested code fences), then the appended fence length is longest-run + 1, in order to preserve verbatim content.
- **Second Ctrl+C grace window**: If a second SIGINT arrives within the grace window during EXECUTING, then the process force-kills, in order to provide an escape hatch for hung commands.

## Key Unknowns
- [x] [Technical] Signal handling feasibility for two-phase Ctrl+C — Resolved via empirical spike: custom SIGINT handler survives group-wide SIGINT while `subprocess.run` is in flight; raising `KeyboardInterrupt` cleanly breaks blocking waits; children must run in their own process group (`start_new_session=True` on POSIX) to survive terminal SIGINT. Findings recorded in the Task Brief.
- [x] [Functional] Pipeline MESSAGE turn persistence semantics — Resolved: user signed off on no report.md / no next turn / `awaiting_reply: true`.

## Implementation Plan
Workstreams ordered A → B → C per the Task Brief (A is the defect fix defining the `awaiting_reply` state B depends on; C is independent but largest).

Key code touch points (verified in Task Brief):
- `SessionOrchestrator.execute()` — guard the `is_session and plan_path` finalize block for pipeline MESSAGE turns.
- `SessionService.get_session_state` / `SessionLifecycleManager.resume` — new AWAITING_REPLY logical state (must consult the meta flag, NOT re-execute).
- `session_repository` — `save_meta`/`load_meta` for `awaiting_reply`.
- `__main__.py` `resume()` + `session_cli_handlers` — `-m` flag threading.
- `core/utils/interrupt_guard.py` (new) — injected InterruptGuard (Constructor Injection only; no module patching; grace window centralized in config).
- `shell_adapter` — `start_new_session=True` on POSIX.

Test strategy: Unit tests drive all logic (pipeline suppression regression, state machine, smart fencing, InterruptGuard phase behavior via self-signaling). A final acceptance Wiring deliverable covers the end-to-end pipeline suppression and `resume -m` flows via the CLI test driver. Anti-mock poisoning: constructor-injected fakes only.

## Deliverables
- [ ] **Contract** - Add `awaiting_reply` flag support to the session meta repository (save/load round-trip) — unit tests.
- [ ] **Logic** - Suppress turn finalization for pipeline MESSAGE turns in `SessionOrchestrator.execute` (skip `finalize_turn`, persist `awaiting_reply: true`, keep terminal printing, return report) — unit regression tests including the non-pipeline control.
- [ ] **Contract** - Add `--message/-m` flag to the `resume` CLI command and thread it through `handle_resume_session` / `_orchestrate_session_loop` into the orchestrator resume chain — unit tests.
- [ ] **Logic** - Extend the resume state machine for AWAITING_REPLY turns (no re-execution; `-m` → clear flag, transition, plan with message; interactive → prompt for reply; non-interactive without message → clean exit with guidance) and skip the interactive prompt for COMPLETE_TURN + `-m` — unit tests.
- [ ] **Logic** - Append a smart-fenced `## User Request` section to the latest `report.md` on COMPLETE_TURN resume with an injected message (extend the smart-fencing helper in `core/utils/markdown.py` for longest-backtick-run computation if needed) — unit tests.
- [ ] **Contract** - Implement `InterruptGuard` in `core/utils/interrupt_guard.py` (SIGINT handler, WAITING/EXECUTING phase context managers, `threading.Event` flag, two-signal escalation, grace window centralized in config) — unit tests.
- [ ] **Wiring** - Wire interrupt phases into the execution orchestrator and session loop (WAITING around `ask_question` and the planning LLM call with immediate-exit on interrupt; EXECUTING around the action loop with INTERRUPTED skip + report generation via `finalize_turn`) — unit tests.
- [ ] **Migration** - Shield in-flight shell commands from terminal SIGINT via `start_new_session=True` on POSIX in `ShellAdapter` (document best-effort Windows behavior) — unit tests.
- [ ] **Wiring** - Acceptance test: end-to-end pipeline MESSAGE turn suppression and `resume -m` flows via the CLI test driver (final behavioral gate for the Gherkin scenarios).

## Implementation Notes
(filled by Developer as deliverables are implemented)

## Verification
- [ ] `uv run pytest tests/suites/unit/core/services/test_pipeline_message_break.py tests/suites/unit/core/services/test_session_lifecycle_manager.py tests/suites/unit/core/utils/test_interrupt_guard.py` — all green.
- [ ] Full suite green via the post-commit hook (never bypassed).
- [ ] Manual: `teddy start -a assistant -p -m "Say hi and ask how I am"` → process exits after the MESSAGE; `.teddy/sessions/<name>/01/` contains NO `report.md`, no `02/` directory; `01/meta.yaml` has `awaiting_reply: true`.
- [ ] Manual: `teddy resume -m "I am great, tell me a joke"` on that session → turn 01 is NOT re-executed; `02/` is created and planned with the injected reply.
- [ ] Manual: `teddy resume -m "new request"` on a fully completed session → `## User Request` appended to the latest `report.md` with a smart-fenced codeblock; next turn planned without interactive prompt; `session_service` recognizes it as a user-request turn.
- [ ] Manual: `teddy start` (interactive), Ctrl+C during a multi-action plan with a long `EXECUTE` (e.g., `sleep 5`) → command completes, remaining actions logged as INTERRUPTED, `report.md` created, process exits. Second Ctrl+C during the sleep → immediate kill.
- [ ] Manual: Ctrl+C during the planning LLM call and during any `ask_question` prompt → immediate exit, no partial artifacts.
