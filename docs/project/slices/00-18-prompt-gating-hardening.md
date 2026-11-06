# Slice: Prompt Gating Hardening
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** [00-17 Require Approval Rename](/docs/project/slices/00-17-require-approval-rename.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** [spikes/debug/prompt-gating-hardening/](/spikes/debug/prompt-gating-hardening/)
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [ConsoleInteractor](/docs/architecture/adapters/outbound/console_interactor.md), [SystemEnvironment](/docs/architecture/core/ports/outbound/system_environment.md)
- **Scope Slug:** `prompt-gating-hardening`

## Goal
Close the remaining prompt sites that do not gate on user presence, so a run without a terminal never waits for input and a run without action approval never loses a prompt a human could answer.

## Context
- `SessionLifecycleManager._can_prompt_user(pipeline)` is today the only presence gate: `not pipeline and ISystemEnvironment.isatty()`, with the pipeline early return taken before the port is consulted.
- The start opening prompt (`src/teddy_executor/adapters/inbound/session_cli_handlers.py:846-849`) fires when `message is None` alone. The module contains no `isatty` reference and no approval reference, so nothing there distinguishes a terminal from piped stdin, and the handler only raises `EOFError` after a prompt returns empty.
- `ConsoleAskLoop.run()` (`src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py`) asks until it gets a non-empty answer and treats `EOFError` as an empty reply. `ConsoleAskLoop._is_tty()` (line 54) reads `sys.stdin.isatty()` directly instead of the `ISystemEnvironment` port, so the loop's own terminal assumption cannot be faked in a test and can diverge from the lifecycle manager's answer.
- `_resume_ready_turn`'s COMPLETE_TURN branch delegates to `_handle_planning_and_execution` without `pipeline=pipeline`, while the EMPTY branch passes it. `pipeline` therefore takes its `False` default downstream, so `_can_prompt_user(False)` can prompt during a pipeline resume.
- `_resolve_blank_message` is the shared blank-message gate: prompt when `_can_prompt_user`, terminate on an empty reply, normalize to absent otherwise. It is wired only into `_resume_ready_turn` (EMPTY/COMPLETE_TURN). The non-awaiting PENDING_PLAN branch never calls it: `_parse_pending_plan` returns `None` for a blank message, so a blank `-m ""` falls to the bare `execute(plan_path=...)` call with no prompt. A non-blank `-m` seeds `plan.metadata["user_request"]` and runs the same plan object through `execute(plan=plan)`.
- A non-awaiting PENDING_PLAN turn comes from aborting at the plan reviewer (`q` → `action_cancel` → `self.exit(None)` → abort prompt → empty answer → `_handle_aborted_session` returns `None` → `session_orchestrator.py:349-357` returns before `finalize_turn`), from Ctrl+C inside the TUI, or from a crash between the plan write and finalization. It keeps `plan.md`, has no `report.md`, and carries no `awaiting_reply` flag (set only by the pipeline MESSAGE stop).
- `_should_consume_awaiting_reply` treats a parsed MESSAGE-only pending plan as awaiting a reply even without the flag, but the plan is only parsed when a message is injected; an awaiting-reply turn with a blank `-m` therefore reaches its own prompt inside `_consume_awaiting_reply` and must keep it.
- `__main__._resolve_setup_editor` is the one gate that combines presence and approval (`isatty() and not pipeline and (interactive or message is None)`). Its docstring already states why the AND is deliberate, so it stays as written.
- `__main__._resolve_setup_api_key` is pure presence (`isatty() and not pipeline`) and is the shape the other gates now follow.
- The abort proceed prompt (`src/teddy_executor/core/services/session_orchestrator.py:505`) is ungated, but it is reachable only after a user-initiated abort, which already required input. Examined and deliberately left unchanged.
- Verification is behavioural only: every requirement below is observable by running the CLI, and no test asserts source text or identifier presence.

## Scenarios
> As a developer, I want every prompt reachable only when a human is at the terminal, so automated runs never wait for input and interactive runs never silently skip a question.

```gherkin
Given stdin is not a terminal and no `-m` is supplied
When `teddy start` runs
Then it exits with a message instead of waiting for input
```

```gherkin
Given a terminal is attached and no `-m` is supplied
When `teddy start` runs
Then it prompts "What are we working on?" and seeds the session with the answer
```

```gherkin
Given a COMPLETE_TURN session, a terminal attached, and pipeline mode
When `teddy resume -m ""` runs
Then it does not prompt and resumes against context
```

```gherkin
Given an awaiting-reply session and no terminal
When `teddy resume` runs
Then it prints the guidance message and exits without prompting
```

```gherkin
Given an awaiting-reply session and a terminal attached
When `teddy resume -m ""` runs
Then it prompts for the reply
```

```gherkin
Given a non-awaiting PENDING_PLAN session and a terminal attached
When `teddy resume -m ""` runs
Then it prompts for the next instruction, the plan reviewer's `m` preview shows the reply, and `report.md` records it under `## User Request`
```

```gherkin
Given a non-awaiting PENDING_PLAN session and `yolo_default: true`
When `teddy resume -m ""` runs at a terminal
Then it prompts for the next instruction and records the reply even though the plan review is skipped
```

## Edge Cases
- **Closed stdin during a prompt**: if the ask loop receives `EOFError`, then that is treated as an empty answer so the caller's termination idiom still applies, and the loop must not spin.
- **Pipeline with a message**: if `--pipeline` is passed with a message, then no prompt of any kind runs, because pipeline mode is the automation path.
- **Missing API key on a terminal with `-y -m`**: if the key is unset, then setup still prompts, because the run cannot proceed without it (unchanged).
- **Start with piped stdin and a message**: if `-m` is supplied, then no prompt runs regardless of terminal state (unchanged).
- **Pipeline start with a blank message**: if `--pipeline` receives `-m ""`, then the pipeline-requires-a-message error wins before any prompt.
- **Non-awaiting PENDING_PLAN with a blank `-m ""` at a terminal**: if a human is reachable, then the branch prompts for the next instruction and runs the pending plan with the reply seeded into `plan.metadata["user_request"]`, so the reviewer's `m` preview shows it and `s` writes `## User Request` to `report.md`; the plan was aborted before execution, so this is its first execution.
- **Non-awaiting PENDING_PLAN with a blank `-m ""` under yolo**: if a human is reachable, then it still prompts and records, because the gate reads user presence, not plan approval; the reviewer step is skipped and the actions run.
- **Non-awaiting PENDING_PLAN with a blank `-m ""` and no terminal**: if `isatty()` is false, then no prompt fires and the bare `execute(plan_path=...)` path stays byte-identical, because there is nobody to ask.
- **Non-awaiting PENDING_PLAN with a blank `-m ""` and an empty reply**: if the prompt returns an empty answer, then the session terminates with no execution and no seeding, using the existing abort idiom.
- **Non-awaiting PENDING_PLAN with an absent `-m`**: if the flag is omitted, then no prompt fires and the pending plan runs, because only an explicit present-but-blank `-m` asks for an instruction.
- **Interrupted MESSAGE-only pending plan**: if the plan parses as a communication turn but the `awaiting_reply` flag is absent, then a reply produced by the blank-`-m` prompt is consumed as that turn's reply — the same path a non-blank `-m` takes — not recorded as `## User Request` on a re-run message plan.
- **Awaiting-reply pending turn with a blank `-m ""`**: if the turn carries `awaiting_reply`, then the awaiting-reply prompt inside `_consume_awaiting_reply` fires as it does today, because the blank-message resolution runs after that short-circuit, so no second prompt appears.

## Key Unknowns
- [x] [Technical] Non-TTY start behaviour: whether `teddy start` with a closed stdin and no `-m` waits in the ask loop today or exits through the handler's `EOFError` guard. Design sensitivity: if it waits, the presence gate is a defect fix and the handler must check presence before prompting; if it already exits, the slice narrows to routing the ask loop's terminal read through the port and loses its headline symptom, so reproduce before changing anything. **Resolved 2026-11-05:** it already exits. With a dummy API key and closed stdin the real CLI reaches the opening prompt and exits code 1 in about 1.5s with `Error: No terminal input provided for initial message.`; without a key the API-key gate correctly declines to fire because no terminal is attached, so the run stops at configuration validation before the prompt. The in-process probe (fake `ISystemEnvironment` reporting `isatty()=False`, empty stdin) shows the ask loop returning `""` after exactly two empty reads (the response prompt and the empty-confirmation prompt) and the handler's empty-message guard terminating the run through `typer.Exit(1)`; the presence port is consulted zero times. Nothing blocks or spins. The headline symptom does not reproduce, so the handler gate is hardening rather than a hang fix, and the port routing stands on testability and consistency grounds.
- [x] [Domain] Blank `-m` on a non-awaiting PENDING_PLAN resume: whether a present-but-blank message should prompt for a new instruction when a human is reachable, run the pending plan with no prompt (today's behaviour), or error. Design sensitivity: prompting could require that branch to plan a new turn instead of running the pending plan, which would be a behaviour change beyond gating and enlarge the slice. **Resolved 2026-11-05, confirmed by the user:** a blank `-m ""` prompts when a human is reachable, seeds the reply into `plan.metadata["user_request"]`, and runs the pending plan as its first execution; with no terminal the branch keeps the bare path, and an empty reply terminates. No new state-machine branch is needed because the reply changes the audit artifact, exactly as pressing `m` in the plan reviewer does: the reviewer preview reads the same field (`textual_plan_reviewer_previews.py:316`), the assembler renders it as `## User Request` (`execution_report_assembler.py:38`, `execution_report.md.j2:297-300`), and the reviewer submit returns the same plan object. The prompt gates on user presence, so a yolo run at a terminal prompts and records too. Measured against the real manager (`probe_pending_plan_message_channel.py`): today's blank `-m` asks nothing and seeds nothing; the one-call fix asks once and runs the seeded plan in both interactive and yolo runs, keeps the bare path without a terminal, and terminates on an empty reply. Confirmed live on 2026-11-05 by aborting a plan at the reviewer and running `teddy resume -m ''`, which ran the pending plan with no prompt. Two ordering constraints follow: the awaiting-reply short-circuit stays first so flagged turns keep their own prompt, and a prompted reply on a MESSAGE-only pending plan takes the same consume-as-reply path a non-blank `-m` takes.

## Impact
1. `[MIGRATE]` `handle_new_session` — gate the opening prompt on presence and, when absent, exit with the existing no-input message instead of entering the ask loop.
2. `[MIGRATE]` `ConsoleAskLoop` — read presence through `ISystemEnvironment`, injected at the composition root where the ask loop is built, so the loop and the lifecycle manager share one presence source.
3. `[MIGRATE]` `SessionLifecycleManager._resume_ready_turn` — pass `pipeline=pipeline` into `_handle_planning_and_execution` in the COMPLETE_TURN branch, matching the EMPTY branch.
4. `[MIGRATE]` `SessionLifecycleManager.resume` non-awaiting PENDING_PLAN branch — resolve a present-but-blank message through the existing `_resolve_blank_message` after the awaiting-reply short-circuit, re-parse the pending plan once a reply exists, and re-check the awaiting-reply predicate so a prompted reply matches the non-blank path. Internal to the branch: no port, DTO, or signature change.
5. `[MIGRATE]` CLI handler, lifecycle, and console adapter suites — the Scenarios and Edge Cases above drive the assertions, including the non-TTY start path, the pipeline COMPLETE_TURN resume, and the pending-plan blank-message cases.
6. `[PRUNE]` `ConsoleAskLoop._is_tty()` — remove the direct `sys.stdin.isatty()` read in favour of the port, keeping `run()`'s termination semantics unchanged.

## Deliverables
- [x] **Wiring** - Reproduce the non-TTY `teddy start` behaviour with a probe under `spikes/debug/prompt-gating-hardening/` and record the observed outcome before changing the handler. Measured: see `FINDINGS.md` beside the probes.
- [x] **Core** - Gate the start opening prompt on user presence, leaving the terminal path unchanged.
- [ ] **Adapter** - Route the ask loop's terminal check through the system-environment port.
- [ ] **Core** - Pass `pipeline` through the COMPLETE_TURN delegation so pipeline resumes never prompt.
- [ ] **Core** - Resolve a blank `-m` on the non-awaiting PENDING_PLAN branch through `_resolve_blank_message`, seed the reply into `plan.metadata["user_request"]`, and run the pending plan as its first execution. Keep the bare path when no terminal is attached, terminate on an empty reply, and keep the awaiting-reply prompt for flagged turns; a prompted reply on a MESSAGE-only pending plan takes the non-blank consume-as-reply path.
- [ ] **Migration** - Update the CLI handler and lifecycle suites so the Scenarios and Edge Cases above drive the assertions.

## Implementation Notes
- 2026-11-05: Prototype ran four probes from `spikes/debug/prompt-gating-hardening/` (real CLI with closed stdin, in-process `handle_new_session` with a fake presence port, replay of the pending-plan resume branch, replay of the blank-message channel with the proposed fix). Findings recorded in `FINDINGS.md` beside them.
- 2026-11-05: The non-TTY start does not wait today; the handler's empty-message guard terminates it after two empty ask-loop reads. The ask loop treats the closed stdin as an empty reply, so it neither raises out of `run()` nor spins.
- 2026-11-05: A missing API key stops `teddy start` at configuration validation before the opening prompt, so verification must supply a key (or exercise `resume`) to reach the prompt path.
- 2026-11-05: `ConsoleAskLoop._is_tty()` ignores the injected port, proven by driving one loop instance against a port reporting `isatty()=False` while stdin flips between piped and TTY.
- 2026-11-05: Domain Key Unknown resolved with the user after a live reproduction: `teddy start -n -m '…'`, `q` at the reviewer, Enter at the abort prompt, then `teddy resume -m ''` ran the pending plan's actions with no prompt and recorded no `## User Request`. The desired behaviour is prompt-and-record, matching the reviewer's `m` key, including under yolo.
- 2026-11-05: `probe_pending_plan_message_channel.py` measured the one-call fix: a blank `-m ""` prompts once and runs the seeded plan in both interactive and yolo runs, no terminal keeps the bare path, and an empty reply terminates.
- 2026-11-05: Two ordering constraints for the Core deliverable. The awaiting-reply short-circuit stays first so flagged turns keep their own prompt. A MESSAGE-only pending plan without the flag is only classified once a reply exists, so a prompted reply must take the same consume-as-reply path a non-blank `-m` takes.
- 2026-11-05: The README's "Pass an empty message to be prompted instead" needs no edit once this slice lands; the pending branch honours it.
- 2026-11-05: Terminology settled: the pending plan was aborted before execution, so running it is its first execution. "Re-execution" is retired.
- 2026-11-06: Start presence gate shipped. `handle_new_session` resolves `ISystemEnvironment` and consults `isatty()` before the opening prompt; with no terminal attached it raises the existing `EOFError` no-input message instead of entering the ask loop. The terminal path is byte-identical: a truthy `isatty` still calls `ask_question("What are we working on?")` and seeds the session with the answer.
- 2026-11-06: Coverage lives in `tests/suites/unit/adapters/inbound/test_session_start_presence_gate.py` (no terminal → exit; terminal → prompt and seed; explicit `-m` → presence never consulted). The resequencing suite migrated its blank-message cases to a truthy presence port, and its obsolete "even when non-interactive" test was deleted because the new module covers that branch.
- 2026-11-06: Integration surfaced 13 acceptance tests that drove `teddy start` with piped stdin and no `-m`, relying on the retired unconditional prompt. They were Local Flaws: `__main__` derives `setup_api_key=isatty() and not pipeline` from the same presence port, so a fake TTY also arms the required-key preflight, and the harness's blank `llm.api_key` would have consumed the piped input at the key prompt. The harness now supplies a default `llm.api_key` (single-sourced with `mock_config`), which short-circuits `_ensure_api_key_configured` at its first line, and each failing test chains `.with_tty(True)` before driving the CLI.
- 2026-11-06: Integration gate green: migrated modules 29 passed, full suite 2253 passed, 5 skipped.

## Verification
1. **Non-TTY start:**
   With a resolvable API key, run `printf '' | teddy start`.
   Confirm the command exits promptly with `Error: No terminal input provided for initial message.` and never waits for input. Without a key the run stops at configuration validation before the prompt, so the key is a prerequisite.
2. **Interactive start:**
   Run `teddy start` in a terminal.
   Confirm it prompts `What are we working on?` and proceeds with the typed answer.
3. **Pipeline resume:**
   Run `teddy resume -p -m ""` on a completed session in a terminal.
   Confirm no prompt appears and the run proceeds against context.
4. **Pending-plan blank resume:**
   Run `teddy start -n -m "list the files in this repository"`, press `q` at the plan reviewer, then press Enter at the abort prompt.
   Run `teddy resume -m ""`.
   Confirm it prompts `What would you like to do next?`, that the reviewer's `m` preview shows the reply when the plan is approved with `s`, and that `report.md` records it under `## User Request`.
5. **Pending-plan blank resume under yolo:**
   With `yolo_default: true`, repeat step 4 on a freshly aborted turn.
   Confirm the prompt still appears and the reply is recorded, even though the plan review is skipped.
