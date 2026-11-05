# Bug: `teddy resume -m ""` Does Not Prompt When `yolo_default: true`
- **Status:** Resolved (fix applied directly to `src/` under explicit user override; `make test` green)
- **Milestone:** Milestone 4: Terminal User Interface
- **Vertical Slice:** [00-11 Empty Message Prompt](/docs/project/slices/00-11-empty-message-prompt.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms
The README documents that an empty `-m` prompts for a multi-line instruction:

```bash
teddy resume -m ""
```

Observed instead: the session resumes straight into planning with no prompt.

```
$ teddy resume -m ''
Checking configurations...
...
Resuming session: .teddy/sessions/20261105_085952-read-latest-vertical-slices-tell-say
[03] read-latest-vertical-slices-tell-say | Waiting for Pathfinder to respond...
```

A second symptom shares the same cause. When the session is left awaiting a reply, the same command prints guidance that contradicts the flag the user just passed:

```
This session is awaiting your reply. Re-run interactively
or inject one with: teddy resume -m '<your reply>'
```

Minimal reproduction: a repository whose `.teddy/config.yaml` sets `yolo_default: true` (the bundled default in `src/teddy_executor/resources/config/config.yaml:35` is `false`), then run `teddy resume -m ''` from a TTY without `-y`, `-n`, or `-p`. The session must be either in `COMPLETE_TURN` (blank-message prompt path) or awaiting a reply (`awaiting_reply` turn).

## Context & Scope
### Regressing Delta
`fddc474f fix(empty-message-prompt): prompt on blank -m at resume boundary` introduced the blank-message prompt in `src/teddy_executor/core/services/session_lifecycle_manager.py` and gated it on the `interactive` flag; `a17100bf` later retitled the prompt constant. The feature is present; the gate's input is wrong.

The second site predates that commit: `_consume_awaiting_reply` gates its reply prompt on `if not reply and interactive:` (line 353), the same wrong signal.

### Environmental Triggers
- `.teddy/config.yaml` line 35: `yolo_default: true` (repository-local; the bundled default in `src/teddy_executor/resources/config/config.yaml:35` is `false`).
- Invocation without `-y`, `-n`, or `-p`.
- A TTY is present, so the process could reach the user for input.

### Ruled Out
- **CLI argument layer:** `resume` declares `message: Optional[str] = typer.Option(None, "-m", "--message")`, so click forwards `''` verbatim. `handle_resume_session` and `_orchestrate_session_loop` forward `message=message` without rewriting it. No `message or None` coercion exists on the resume path.
- **Flag-presence collapse:** The `-m` default is `None`, so a present-but-blank `''` stays distinguishable from an omitted flag all the way into the lifecycle manager.
- **`_resolve_blank_message` itself:** With `interactive=True` it prompts via `ask_question(_NEXT_INSTRUCTION_PROMPT)` and terminates the session on an empty reply. The method is correct in isolation; only its gate input is wrong.
- **Editor-prompt path:** `prompt_for_message` has no production caller on the resume path; the resume prompt is `ask_question`-based, not editor-based.
- **`PENDING_PLAN` non-awaiting branch:** the reported session was in `COMPLETE_TURN` (turns 01-02 carry `finish_reason: stop`; turn 03 was created by the resume and left unfinished when the user pressed `q`), so that branch — which still has no blank-message resolution — is unrelated to this symptom.
- **Absent terminal as the trigger:** the reported run had a TTY. The bug reproduces only *with* a terminal, because without one there is nobody to prompt.

## Diagnostic Analysis
### Causal Model
One boolean carries two unrelated meanings, and both resume prompt sites read the wrong one.

1. `__main__.py:570` computes `interactive = not (_resolve_yolo(yolo, config_service) or pipeline)`.
2. `_resolve_yolo(None, config_service)` falls back to `config_service.get_setting("yolo_default", False)`. With `yolo_default: true`, it returns `True`.
3. `interactive` is therefore `False` even though the user invoked the command from a TTY without any automatic-approval intent flag.
4. `interactive` is an action-approval flag: `_handle_planning_and_execution` forwards it to `orchestrator.execute(interactive=...)`, where it decides whether each action needs confirmation.
5. Both prompt decisions read that same flag instead of asking whether a human is reachable:
    - `_resume_ready_turn` calls `_resolve_blank_message('', interactive)`. Its second branch returns `(None, False)` when `not interactive`, silently normalizing the deliberately-blank message to absent without calling `ask_question`.
    - `_consume_awaiting_reply` skips its reply prompt (`if not reply and interactive:`), falling through to `display_message`, which tells a user who just passed `-m ""` to "re-run interactively or inject one with `resume -m`".
6. With `message=None`, `trigger_new_plan` runs the planner, which emits the `[NN] ... | Waiting for X to respond...` banner. That is the reported observation.
7. User presence is already expressible: `ISystemEnvironment.isatty()` exists as an outbound port (`system_environment.py:27`, adapter wraps `sys.stdin.isatty()`), and `__main__.py:97` already gates editor setup on `system_env.isatty() and not pipeline and (interactive or message is None)`. Presence means "a terminal is attached and the run is not a pipeline", never the action-approval flag.
8. The replacement gate must keep the TTY check rather than drop the guard: `ConsoleAskLoop.run()` loops forever on a non-TTY stdin (it swallows `EOFError` as `""` and retries), so an unguarded prompt hangs a piped run.

### Discrepancies
- [x] The README promises a prompt for `teddy resume -m ""`; the observed run started planning with no prompt. (Resolved: the gate reads the action-approval flag, which `yolo_default: true` forces to False. MRE 01 reproduces the symptom; MRE 02 fixes it.)
- [x] `interactive` conflates two orthogonal concerns: "auto-approve actions" (yolo/pipeline) and "can reach the user for input". (Resolved: presence is expressed as `not pipeline and system_environment.isatty()`, mirroring the `_resolve_setup_editor` precedent; `interactive` keeps its action-approval meaning.)
- [x] Blank `-m` is silently normalized even though the user typed the flag deliberately, making the request behaviorally indistinguishable from a flag omission. (Resolved: `_resolve_blank_message` returned `(None, False)` on `not interactive`; the replica gates on presence instead.)
- [x] An awaiting-reply session resumed with a blank `-m` printed "Re-run interactively or inject one with: teddy resume -m ..." — nonsensical advice to a user who just supplied `-m`. (Resolved: `_consume_awaiting_reply` carried the same `interactive` gate; the replica routes both sites through `_can_prompt_user(pipeline)`.)
- [x] Dropping the guard outright would hang piped runs, because `ConsoleAskLoop.run()` busy-loops on a non-TTY stdin. (Resolved: the replacement gate requires `isatty()`; scenarios B and F pin the no-TTY behaviour on both sites.)
- [x] The introducing slice words its criterion as "if stdin is not interactive ... because a non-interactive run cannot block on a prompt", which is about terminal availability, not yolo. (Resolved: the fix restores the slice's stated intent, so this is a defect repair rather than a product decision.)

### Investigation History
1. Located the resume state machine (`SessionLifecycleManager.resume`) and the documented blank-message prompt feature; confirmed the feature exists and is scoped to a present-but-blank `-m`.
2. Read the CLI declaration and handler wiring; confirmed `-m` defaults to `None` and `''` is forwarded verbatim.
3. Enumerated callers of `prompt_for_message`; found no resume-path caller, so the prompt is `ask_question`-based rather than editor-based.
4. Read `_resolve_blank_message` and `_resume_ready_turn`; identified `interactive` as the deciding input.
5. Read `_orchestrate_session_loop` and `_resolve_yolo`; found `.teddy/config.yaml` sets `yolo_default: true`, so `interactive` resolves `False` for the reported run.
6. Built MRE 01, driving `_resolve_yolo` against a fake live config and `_resolve_blank_message` against a recording interactor; observed `interactive=False`, `message=None`, `terminated=False`, zero prompts, while the `interactive=True` control prompted once and terminated. Symptom reproduced deterministically with no LLM and no session filesystem.
7. Inspected the reported session's turn metadata; turns 01-02 carry `finish_reason: stop` and turn 03 carries none (created by the resume, interrupted by `q`), proving the run started from `COMPLETE_TURN` and reached `_resolve_blank_message`.
8. Read `ISystemEnvironment`; found `isatty()` already exists as an outbound port, and `__main__.py:97` already gates editor setup on `isatty() and not pipeline`, never on yolo.
9. Read `ConsoleAskLoop.run()`; found an unbounded `while True` loop that swallows `EOFError` as `""`, so `ask_question` busy-loops on a non-TTY stdin. This makes the existing guard load-bearing: the replacement must keep a TTY check.
10. Read `SessionPorts` and its composition-root factory; found no system-environment port and zero `ISystemEnvironment` references in `container.py`, so a TTY signal had to be threaded in. Every `SessionPorts(...)` site (the factory plus 13 test fixtures) constructs with keyword arguments.
11. Read `_consume_awaiting_reply`; found the same `interactive` gate on the reply prompt plus a `display_message` fallback that misdirects a user who already passed `-m`.
12. Read slice `00-11-empty-message-prompt.md`; its acceptance criteria gate the prompt on stdin interactivity "because a non-interactive run cannot block", confirming presence as the intended signal.
13. Built the replica with one presence helper (`_can_prompt_user(pipeline)` = `not pipeline and system_environment.isatty()`) used at both sites; MRE 02 printed 16/16 PASS across scenarios A-F and FIX VERIFIED, while MRE 01 still reproduces on unmodified production.
14. Applied the change to `src/` under the user's explicit override of the Developer handoff: `SessionPorts.system_environment` (defaulted, `TYPE_CHECKING`), container injection, `_can_prompt_user(pipeline)`, both gate sites, and the `ARCHITECTURE.md` Ubiquitous Language entries for Action Approval and User Presence. A smoke script printed the truth table `(tty, not pipeline) -> True`, `(tty, pipeline) -> False`, `(no tty, not pipeline) -> False`; `ruff check` was clean on all changed files.
15. Rewrote both gate-encoding test modules (no-TTY cases plus yolo-plus-TTY regressions) and ran the full suite: one failure, the pipeline stop-again fixture tripping the assert with `pipeline=True`. Concluded a pipeline run can never prompt, so `_can_prompt_user` now returns `False` before consulting the port. Re-ran MRE 02 (16/16 PASS) and the full suite: 2249 passed, 5 skipped.

## Solution
### Root Cause
The resume prompt sites gate on the action-approval flag `interactive`, which `__main__.py` derives from yolo and pipeline. With `yolo_default: true` in `.teddy/config.yaml`, `interactive` is `False` even though a human is sitting at a TTY, so `_resolve_blank_message` silently normalizes `-m ""` to absent (planning proceeds with no instruction) and `_consume_awaiting_reply` skips its reply prompt in favor of misdirecting guidance. One boolean carried two meanings; user presence is the correct signal and was already available as `ISystemEnvironment.isatty()`.

The fix was proven first in the sandbox replica (`spikes/debug/blank-resume-message-prompt/replica_session_lifecycle_manager.py`) across six scenarios, then applied directly to `src/` under the user's explicit override of the Developer handoff (the change spans three production files plus test rewrites, beyond the single-file threshold that normally routes to the Developer). Both gates now route through one `_can_prompt_user(pipeline)` helper: a pipeline run returns `False` without touching the terminal port, otherwise the helper asserts the injected port and consults `isatty()`. `interactive` keeps its action-approval meaning. MRE 02 still passes 16/16 against the replica; the full suite (2249 passed, 5 skipped) verifies the production change.

### Affected Components
- `SessionLifecycleManager` (`src/teddy_executor/core/services/session_lifecycle_manager.py`): applied. The constructor stores `ports.system_environment`; `_can_prompt_user(pipeline)` returns `False` for pipeline runs without touching the port, otherwise asserts the port and returns `isatty()`; `_resolve_blank_message` takes `pipeline` and calls the helper; `_consume_awaiting_reply` calls the helper in place of `if not reply and interactive:`; `_resume_ready_turn` passes `pipeline` at the call site.
- `SessionPorts` (`src/teddy_executor/core/domain/models/planning_ports.py`): applied. `system_environment: Optional[ISystemEnvironment] = None` sits beside the other optional fields, imported under `TYPE_CHECKING`.
- `container.py` (composition root): applied. The local port-import block gains `ISystemEnvironment` and the `SessionPorts` factory passes `system_environment=container.resolve(ISystemEnvironment)`; the port was already registered as a transient factory, so no new registration was needed.
- `docs/architecture/ARCHITECTURE.md`: applied. The Ubiquitous Language section now defines **Action Approval (`interactive`)** and **User Presence**, with the rule that prompt decisions gate on presence and approval gates on the flag.
- `tests/suites/unit/core/services/test_session_lifecycle_blank_message.py`: applied. Both former `test_non_interactive_blank_message_resumes_without_prompt` cases are now `test_blank_message_without_a_terminal_resumes_without_prompt`, and each state class gained a `test_yolo_blank_message_prompts_when_a_terminal_is_attached` regression case; the fixture pins `isatty` to `False` and prompt cases flip it.
- `tests/suites/unit/core/services/test_session_lifecycle_awaiting_reply.py`: applied. The former `interactive=False` guidance case is now `test_without_terminal_exits_cleanly_with_guidance`, and `test_yolo_prompts_for_reply_when_a_terminal_is_attached` covers the fixed behaviour; the fixture injects the port with `isatty` pinned `False`.
- Remaining `SessionPorts(...)` fixtures: no changes needed. The only fixture that reached a prompt site without the port was the pipeline stop-again module, and the pipeline early return removed that false positive structurally instead of adding a fake terminal to a scenario that can never prompt.
- `docs/project/slices/00-11-empty-message-prompt.md`: applied. A "Gate correction - user presence, not action approval" subsection now follows the slice's implementation notes, recording that the original `interactive` gate was superseded by the User Presence rule and linking this case file.
- Unchanged by design: `IUserInteractor` and `ISystemEnvironment` contracts, and every caller of `interactive` that governs action approval.

### Implementation Notes
The `SessionPorts` field is additive with a default, so the contract stayed non-breaking. The change landed in the contract-first order: field plus container wiring, then the presence helper and both gate sites, then the two test modules, then the Ubiquitous Language entries. The first full-suite run surfaced exactly one failure — the pipeline stop-again fixture reaching the assert with `pipeline=True` — which was resolved structurally by returning `False` for pipeline runs before the port is consulted, not by injecting a terminal double into a scenario that can never prompt.

Adjacent inconsistencies observed and left as debt, not folded into this change: `_resume_ready_turn`'s `COMPLETE_TURN` branch omits `pipeline=` when delegating to `_handle_planning_and_execution` (the `EMPTY` branch passes it), `ConsoleAskLoop._is_tty()` calls `sys.stdin.isatty()` directly despite having `ISystemEnvironment` injected, and the `PENDING_PLAN` non-awaiting resume path still has no blank-message resolution (flagged for its own case file).

### Reproduction Artifacts
- Symptom MRE (targets the pre-fix gate; preserved as the reproduction record): `spikes/debug/blank-resume-message-prompt/01-blank-message-no-prompt-mre.py`
- Fix verification MRE (replica, 16/16 PASS): `spikes/debug/blank-resume-message-prompt/02-fix-verification-mre.py`
- Sandbox replica with the proposed fix: `spikes/debug/blank-resume-message-prompt/replica_session_lifecycle_manager.py`
