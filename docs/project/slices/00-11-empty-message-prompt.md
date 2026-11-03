# Slice: Empty Message Ask-Loop
- **Status:** Planned
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [PromptManager](/docs/architecture/core/services/prompt_manager.md)
- **Scope Slug:** `empty-message-prompt`

## Goal
Make a present-but-empty `-m` prompt the user interactively on both `start` and `resume`, while a fully-absent `-m` resumes without requiring a message, so a user who passes an empty flag is never silently planned against nothing.

## Context
Static findings across the CLI handlers, the prompt manager, and the lifecycle state machine:
- `handle_new_session` (`__main__.py` handler in `session_cli_handlers.py`): prompts `"What are we working on?"` only when `message is None`; its pipeline guard rejects `None` but not `""`. An empty `-m` therefore seeds no `initial_request.md` (`SessionService` skips a falsy request) and plans against context.
- `handle_resume_session`: threads `message` verbatim into `_orchestrate_session_loop` → `SessionOrchestrator.resume`, which delegates directly to `SessionLifecycleManager.resume` with no empty-message guard.
- `PromptManager.resolve_message`: `""` returns `""` (a continuation signal); `None` on turn `01` falls back to `initial_request.md`; any non-`None` value that is blank after resolution returns `None`.
- `SessionLifecycleManager.resume`: the EMPTY and COMPLETE_TURN branches key on truthiness (`if message:`), so `""` and `None` collapse and both plan against context without prompting. The PENDING awaiting-reply branch (`_consume_awaiting_reply`) already prompts on an empty reply when interactive; the PENDING non-awaiting branch re-executes a pending plan and ignores the message.
- `SessionOrchestrator.execute`: keeps its empty-message termination guard (`message is not None and not message.strip()` → `None`). This is the execution path and stays unchanged.

## Scenarios
Primary user journeys and happy paths.

> As a developer, I want an empty `-m` to open the message prompt so I can type my instruction interactively instead of passing a broken flag.

```gherkin
Given a terminal is attached and I am not in pipeline mode
When I run `teddy start -m ""`
Then TeDDy prompts "What are we working on?"
And a non-empty answer seeds the session's initial request
```

```gherkin
Given a terminal is attached
When I run `teddy start` with no `-m`
Then TeDDy prompts "What are we working on?"
```

```gherkin
Given an existing session at a complete or empty turn
And a terminal is attached
When I run `teddy resume -m ""`
Then TeDDy prompts for the next instruction before planning
```

```gherkin
Given an existing session
When I run `teddy resume` with no `-m`
Then the session resumes without prompting for a message
```

```gherkin
Given pipeline mode
When I run `teddy start -p -m ""`
Then the command exits with the pipeline-requires-a-message error
```

## Edge Cases
Boundary conditions and validation cases.
- **Whitespace-only `-m`** (e.g. `"   "`): treated as empty, because trimming is what the user means by an empty flag.
- **Interactive empty reply to the prompt**: if the answer to the prompted message is empty, then the session terminates, because the abort idiom (an empty `ask_question` reply terminates) is preserved.
- **Non-interactive resume with empty `-m`** (`-y -m ""`): if stdin is not interactive, then the empty message normalizes to absent and the session resumes against context, because a non-interactive run cannot block on a prompt.
- **Awaiting-reply session with `-m ""`**: prompts on the empty reply via the existing `_consume_awaiting_reply` path, because the agent's message must print before the reply prompt is shown.
- **PENDING non-awaiting session with `-m ""`**: the message is ignored (a pending plan re-executes), because no new instruction is consumed mid-turn.
- **Start with whitespace `-m` and no terminal** (`-y -m "   "`): normalized to absent, so the run continues without an initial request rather than blocking.
- **Non-empty `-m`**: unchanged everywhere — it is threaded as the message or reply exactly as today.

## Key Unknowns
None. Every behavior is derivable by static reading and is captured under Context.

## Impact
Affected components, migrated in non-breaking steps.
1. `[MIGRATE]` `handle_new_session` — normalize a whitespace-only or empty `-m` to absent before its pipeline guard and opening prompt, so `start` prompts interactively and pipeline mode errors on empty.
2. `[MIGRATE]` `SessionLifecycleManager.resume` — in the EMPTY and COMPLETE_TURN branches, resolve a present-but-blank `message` to an interactive prompt when interactive (terminate on an empty reply) and to absent when non-interactive; leave the awaiting-reply and non-awaiting branches unchanged.
3. `[MIGRATE]` Existing start and resume tests — pin the new empty-`-m` prompting and pipeline behavior.

## Deliverables
- [ ] **Wiring** - Normalize a whitespace-only or empty `-m` to absent at the `start` boundary so the existing opening prompt fires interactively and pipeline mode errors on empty.
- [ ] **Core** - Resolve a present-but-blank `-m` in the EMPTY and COMPLETE_TURN `resume` branches to an interactive prompt when interactive (empty reply terminates) and to absent when non-interactive.
- [ ] **Migration** - Update the start and resume test suites to pin empty-`-m` prompting, bare-`resume` proceeding, and the pipeline-empty error split.

## Implementation Notes

## Verification
1. **Interactive start with empty `-m`:**
   Run `teddy start -m ""` in a terminal.
   Verify TeDDy prompts `What are we working on?` and proceeds with the typed answer.
2. **Interactive resume with empty `-m`:**
   Run `teddy resume -m ""` on a completed session in a terminal.
   Verify TeDDy prompts for the next instruction before planning.
3. **Bare resume:**
   Run `teddy resume` on a completed session.
   Verify no message prompt appears and the session resumes.
4. **Pipeline empty `-m`:**
   Run `teddy start -p -m ""`.
   Verify it exits with `Pipeline mode requires an initial message via -m/--message.`
