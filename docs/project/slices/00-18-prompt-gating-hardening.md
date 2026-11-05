# Slice: Prompt Gating Hardening
- **Status:** Planned
- **Milestone:** N/A (ad-hoc)
- **Depends On:** [00-17 Require Approval Rename](/docs/project/slices/00-17-require-approval-rename.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [ConsoleInteractor](/docs/architecture/adapters/outbound/console_interactor.md), [SystemEnvironment](/docs/architecture/core/ports/outbound/system_environment.md)
- **Scope Slug:** `prompt-gating-hardening`

## Goal
Close the remaining prompt sites that do not gate on user presence, so a run without a terminal never waits for input and a run without action approval never loses a prompt a human could answer.

## Context
- `SessionLifecycleManager._can_prompt_user(pipeline)` is today the only presence gate: `not pipeline and ISystemEnvironment.isatty()`, with the pipeline early return taken before the port is consulted.
- The start opening prompt (`src/teddy_executor/adapters/inbound/session_cli_handlers.py:846-849`) fires when `message is None` alone. The module contains no `isatty` reference and no approval reference, so nothing there distinguishes a terminal from piped stdin, and the handler only raises `EOFError` after a prompt returns empty.
- `ConsoleAskLoop.run()` (`src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py`) asks until it gets a non-empty answer and treats `EOFError` as an empty reply. `ConsoleAskLoop._is_tty()` (line 54) reads `sys.stdin.isatty()` directly instead of the `ISystemEnvironment` port, so the loop's own terminal assumption cannot be faked in a test and can diverge from the lifecycle manager's answer.
- `_resume_ready_turn`'s COMPLETE_TURN branch delegates to `_handle_planning_and_execution` without `pipeline=pipeline`, while the EMPTY branch passes it. `pipeline` therefore takes its `False` default downstream, so `_can_prompt_user(False)` can prompt during a pipeline resume.
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

## Edge Cases
- **Closed stdin during a prompt**: if the ask loop receives `EOFError`, then that is treated as an empty answer so the caller's termination idiom still applies, and the loop must not spin.
- **Pipeline with a message**: if `--pipeline` is passed with a message, then no prompt of any kind runs, because pipeline mode is the automation path.
- **Missing API key on a terminal with `-y -m`**: if the key is unset, then setup still prompts, because the run cannot proceed without it (unchanged).
- **Start with piped stdin and a message**: if `-m` is supplied, then no prompt runs regardless of terminal state (unchanged).
- **Pipeline start with a blank message**: if `--pipeline` receives `-m ""`, then the pipeline-requires-a-message error wins before any prompt.
- **Non-awaiting PENDING_PLAN with a blank message**: undecided; see Key Unknowns.

## Key Unknowns
- [ ] [Technical] Non-TTY start behaviour: whether `teddy start` with a closed stdin and no `-m` waits in the ask loop today or exits through the handler's `EOFError` guard. Design sensitivity: if it waits, the presence gate is a defect fix and the handler must check presence before prompting; if it already exits, the slice narrows to routing the ask loop's terminal read through the port and loses its headline symptom, so reproduce before changing anything.
- [ ] [Domain] Blank `-m` on a non-awaiting PENDING_PLAN resume: whether a present-but-blank message should prompt for a new instruction when a human is reachable, keep re-executing the pending plan (today's behaviour), or error. Design sensitivity: prompting requires that branch to plan a new turn instead of re-executing, which is a behaviour change beyond gating and enlarges the slice; keeping today's behaviour keeps the slice to gates and leaves the gap documented.

## Impact
1. `[MIGRATE]` `handle_new_session` — gate the opening prompt on presence and, when absent, exit with the existing no-input message instead of entering the ask loop.
2. `[MIGRATE]` `ConsoleAskLoop` — read presence through `ISystemEnvironment`, injected at the composition root where the ask loop is built, so the loop and the lifecycle manager share one presence source.
3. `[MIGRATE]` `SessionLifecycleManager._resume_ready_turn` — pass `pipeline=pipeline` into `_handle_planning_and_execution` in the COMPLETE_TURN branch, matching the EMPTY branch.
4. `[MIGRATE]` CLI handler and console adapter suites — the Scenarios and Edge Cases above drive the assertions, including the non-TTY start path and the pipeline COMPLETE_TURN resume.
5. `[PRUNE]` `ConsoleAskLoop._is_tty()` — remove the direct `sys.stdin.isatty()` read in favour of the port, keeping `run()`'s termination semantics unchanged.

## Deliverables
- [ ] **Wiring** - Reproduce the non-TTY `teddy start` behaviour with a probe under `spikes/debug/prompt-gating-hardening/` and record the observed outcome before changing the handler.
- [ ] **Core** - Gate the start opening prompt on user presence, leaving the terminal path unchanged.
- [ ] **Adapter** - Route the ask loop's terminal check through the system-environment port.
- [ ] **Core** - Pass `pipeline` through the COMPLETE_TURN delegation so pipeline resumes never prompt.
- [ ] **Migration** - Update the CLI handler and lifecycle suites so the Scenarios and Edge Cases above drive the assertions.

## Implementation Notes
Planned; no implementation notes yet.

## Verification
1. **Non-TTY start:**
   Run `printf '' | teddy start`.
   Confirm the command exits promptly with a message and never waits for input.
2. **Interactive start:**
   Run `teddy start` in a terminal.
   Confirm it prompts `What are we working on?` and proceeds with the typed answer.
3. **Pipeline resume:**
   Run `teddy resume -p -m ""` on a completed session in a terminal.
   Confirm no prompt appears and the run proceeds against context.
