# Slice: Interruptible `execute` Run
- **Status:** Planned
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `interruptible-execute`

## Goal
Give the stateless `execute` command the same two-phase interrupt bracket the session loop already owns — through one hoisted seam, so the process keeps exactly one owner of the global SIGINT disposition — so `q` and Ctrl+C drain gracefully there too and the previous disposition is restored on every exit path.

## Context
- Session loop owner (`src/teddy_executor/adapters/inbound/session_cli_handlers.py`): Resolves `InterruptGuard`, calls `previous_handler = interrupt_guard.install()`, resolves `IQuitKeyListener`, calls `quit_listener.start()`, and in a `finally` stops the listener and restores the previous disposition. The guard is a `punq.Scope.singleton` on purpose, because signal disposition is process-global.
- Stateless path (`src/teddy_executor/adapters/inbound/cli_helpers.py`): Resolves `IRunPlanUseCase` and runs it directly, with no handler install and no quit-key listener, so a Ctrl+C during `execute` escapes as a traceback and a bare `q` is never self-delivered as SIGINT.
- Reviewer mount point: The reviewer is mounted inside `orchestrator.execute`, so the listener must already be live while the TUI is up. The reviewer's own `q` binding stays authoritative there, and the `stdin_owned()` claim (used by `TextualPlanReviewer` and the console interactor) is what keeps the raw reader off Textual's keys.
- Interrupt naming: `format_interrupt_notice(guard.source)` reports which key fired, and a drained run still writes its report with status `INTERRUPTED`.
- Owning invariant: `boundary_owns_interrupt_lifecycle` in the CLI adapter component page states the session-loop-only ownership this slice removes.
- Why one seam: Two owners each taking their own `install()` snapshot would restore each other's handler, so the lifecycle cannot simply be copied into the `execute` path.

## Scenarios

> As an operator, I want Ctrl+C during a stateless run to end it cleanly instead of printing a traceback.

```gherkin
Given a plan whose EXECUTE action sleeps for 30 seconds
When I run it through teddy execute and press Ctrl+C
Then the run stops with the interrupt notice naming the pressed key
And report.md records status INTERRUPTED
And the shell prompt returns with the previous SIGINT disposition restored
```

> As an operator, I want a bare `q` to behave the same way in execute as it does in a session.

```gherkin
Given the same long-running plan executed through teddy execute
When I press q
Then the guard runs the same drain the session loop runs
And the report records status INTERRUPTED
```

> As an operator, I want my terminal usable after the run whatever ended it.

```gherkin
Given an execute run that fails validation before any action runs
When the command exits
Then the previous SIGINT disposition is restored and the next Ctrl+C in the shell behaves normally
```

## Edge Cases
- **Failure inside the bracket**: If an action raises during the run, then the `finally` still stops the listener and restores the disposition, because a failed run must not leave the process with a foreign handler.
- **`typer.Exit` raised inside**: If the orchestrator raises `typer.Exit` (a validation failure does), then the bracket unwinds through the same `finally`, because exit codes must not bypass restoration.
- **Non-TTY stdin**: If stdin is not a terminal, then the quit-key listener starts as a no-op and no key reading happens, because a pipeline run must never block on input.
- **Second press during drain**: If a second `q` or Ctrl+C arrives while the first drain is unwinding, then the second press is ignored, because the guard already committed to the current phase.
- **Double install**: If the seam is entered while the guard is already installed by the same process, then it raises a `TeddyError` naming the existing owner rather than silently restoring a foreign handler.
- **Reviewer dismissed**: If the user abandons the review before approving, then the listener stops with the plan never executing, because the bracket covers review and execution alike.
- **KeyboardInterrupt while waiting**: If an interrupt lands while the run waits for a model response, then the notice prints instead of a traceback, because waiting is the most likely moment for a stray Ctrl+C.

## Key Unknowns
- None. The bracket the session loop already proves is the exact shape to hoist, the owning invariant names what flips, and every branch above is already observable through the existing guard and listener fakes.

## Impact
1. `[NEW]` `interrupt_scope(container)` in `src/teddy_executor/adapters/inbound/interrupt_scope.py` — one context manager that installs the guard, starts the listener, and restores both in `finally`, refusing a nested install.
2. `[MIGRATE]` The session loop in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — replace its inline install/start/finally block with the seam, keeping behaviour identical.
3. `[MIGRATE]` The stateless execute handler in `src/teddy_executor/adapters/inbound/cli_helpers.py` — bracket its `IRunPlanUseCase` invocation with the seam.
4. `[MIGRATE]` `docs/architecture/adapters/inbound/cli.md` — flip `boundary_owns_interrupt_lifecycle` from session-only to both boundaries.
5. `[NEW]` An acceptance test proving an interrupted `execute` run writes an `INTERRUPTED` report and leaves the disposition restored.
6. `[MIGRATE]` The reviewer component page — record that the shared bracket runs during review, so a session and an `execute` run present the same key semantics.

## Deliverables
- [ ] **Interface** — Define `interrupt_scope` as a context manager over the injected guard and listener, with the nested-install rejection documented in its contract.
- [ ] **Harness** — Extend the interrupt and quit-key doubles so a test can simulate a press during review, during execution, and during waiting, and can assert the restore happened exactly once.
- [ ] **Wiring** — Move the session loop onto the seam unchanged and prove the existing session interrupt tests stay green, completing the tracer bullet before `execute` adopts anything.
- [ ] **Adapter** — Bracket the stateless execute handler with the seam and add the acceptance test for an interrupted run.
- [ ] **Cleanup** — Flip `boundary_owns_interrupt_lifecycle` in the CLI component page and record the `execute` key semantics in the reviewer page.

## Implementation Notes

## Verification
1. **Interrupted stateless run:**
   Run `uv run teddy execute --plan-content <plan with a 30s sleep>` and press Ctrl+C.
   Verify the interrupt notice prints, `report.md` says `INTERRUPTED`, and no traceback appears.
2. **Session parity:**
   Run `uv run teddy start -y -m "explore the repo"` and press `q` mid-turn.
   Verify the drain behaves exactly as before the refactor.
3. **Terminal restored:**
   After either run, press Ctrl+C at an empty prompt.
   Verify the shell interrupts normally rather than exiting or ignoring the key.
