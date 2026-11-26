# Slice: Interruptible `execute` Run
- **Status:** In Progress
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

- Real bracket site: the `execute` command body in `src/teddy_executor/__main__.py` runs plan resolution, the use case, the invalid-plan handler, and the report gate inline. The `execute_valid_plan` helper in `cli_helpers.py` has no callers.
- Container lifetime: `get_container()` memoizes one module-level container, so the singleton guard outlives a single in-process command; restoring the disposition must release the claim rather than latch it.
- Status surface: a stateless run has no turn directory, so the drain surfaces `RunStatus.INTERRUPTED` in the printed report, and the report gate exits non-zero only for failures.

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
- **Nested install**: If the seam is entered while the guard still owns the process disposition, then the guard's install contract fails fast with an assertion naming the held disposition instead of silently restoring a foreign handler, because the precondition is a programming defect and must stay strippable from a release build.
- **Sequential runs**: If a later command installs after the first released its claim, then it installs normally, because one memoized container keeps a single guard instance alive across in-process commands and a claim it no longer holds must not block the next legitimate bracket.
- **Reviewer dismissed**: If the user abandons the review before approving, then the listener stops with the plan never executing, because the bracket covers review and execution alike.
- **KeyboardInterrupt while waiting**: If an interrupt lands while the run waits for a model response, then the notice prints instead of a traceback, because waiting is the most likely moment for a stray Ctrl+C.

## Key Unknowns
- None. The bracket the session loop already proves is the exact shape to hoist, the owning invariant names what flips, and every branch above is already observable through the existing guard and listener fakes.

## Impact
1. `[EXTEND]` `InterruptGuard` in `src/teddy_executor/core/utils/interrupt_guard.py` - `install()` keeps returning the previous disposition and additionally records the claim, asserting against a second install; `restore()` reinstates the captured disposition and releases the claim.
2. `[NEW]` `interrupt_scope(guard, listener)` in `src/teddy_executor/adapters/inbound/interrupt_scope.py` - one context manager over the injected guard and listener that installs the guard, starts the listener, and stops and restores both in `finally`.
3. `[MIGRATE]` The session loop in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` - replace its inline install, start, and restore block with the seam, keeping behaviour identical.
4. `[MIGRATE]` The stateless `execute` command body in `src/teddy_executor/__main__.py` - bracket plan resolution, the use-case invocation, the invalid-plan handler, and the report gate with the seam, and surface the interrupt notice instead of a traceback.
5. `[EXTEND]` `tests/harness/setup/sigint_delivery.py` - add a mode that routes a simulated press through whichever SIGINT handler is currently installed, so an in-process acceptance run drives the real guard.
6. `[NEW]` An acceptance test proving an interrupted `execute` run prints an `INTERRUPTED` report, restores the disposition, and prints no traceback.
7. `[MIGRATE]` `docs/architecture/adapters/inbound/cli.md` - flip `boundary_owns_interrupt_lifecycle` from session-only to both boundaries.
8. `[MIGRATE]` The reviewer component page - record that the shared bracket runs during review, so a session and an `execute` run present the same key semantics.
9. `[PRUNE]` `execute_valid_plan` in `src/teddy_executor/adapters/inbound/cli_helpers.py` - no callers; deleting it retires the stray debug print in the same stroke.

## Deliverables
- [x] **Interface** - Give `InterruptGuard` install ownership: `install()` still returns the previous disposition but also records the claim, a second install fails its contract assertion naming the held disposition, and `restore()` reinstates the disposition and releases the claim.
- [ ] **Interface** - Define `interrupt_scope(guard, listener)` as a context manager over the injected guard and listener, stopping the listener and releasing the claim in `finally` on every exit path including a raised exit.
- [ ] **Harness** - Extend the SIGINT delivery double so a simulated press routes through the currently installed handler, letting an acceptance test drive the real guard without raising in the test process.
- [ ] **Wiring** - Move the session loop onto the seam unchanged and prove the existing session interrupt and quit-listener tests stay green before the stateless path adopts anything.
- [ ] **Adapter** - Bracket the stateless `execute` command body with the seam, surface the interrupt notice at that boundary, and add the acceptance test for an interrupted run.
- [ ] **Cleanup** - Flip `boundary_owns_interrupt_lifecycle` in the CLI component page, record the `execute` key semantics in the reviewer page, and prune the dead `execute_valid_plan` helper.

## Implementation Notes

**Audit before implementation (re-partition).** The original Impact and Deliverables lists did not survive the code audit:

- The single Interface deliverable was not atomic: the seam cannot refuse a nested install on its own, because only the guard holds the process-global disposition, so the guard's ownership contract and `restore()` land first.
- The nested-install rejection was worded as a raised domain error, but it is a precondition on a programming defect, so it is a runtime assertion naming the held disposition and stays strippable from a release build.
- The named bracket site, `execute_valid_plan`, has no callers. The live path is the inline body of the `execute` command, which is what the Adapter deliverable brackets.
- `get_container()` memoizes one module-level container, so the singleton guard outlives a single command. `restore()` releases the claim instead of refusing a later bracket, keeping two sequential in-process runs legal while a genuine nested install still fails.
- A stateless run has no turn directory, so the drained status surfaces in the printed report, not in a turn report file. Both scenario wordings were corrected.
- The harness already ships a SIGINT delivery double, a container stub, and a quit-key listener fake, so its deliverable is a thin extension, and no acceptance test currently touches `signal`.
- A stateless interrupt in the waiting phase must not escape as a traceback: the `execute` boundary needs its own notice, because the orchestrator only stamps the drain reason onto skipped actions and never prints one.

**Deliverable 1 — guard install ownership (delivered).**

- `install()` keeps returning the captured disposition, records it in a sentinel-backed field, and asserts against a held claim; `restore()` reinstates that disposition and clears the claim. Ownership uses a dedicated sentinel rather than `None`, because `signal.getsignal()` may legitimately return `None` for a handler not set from Python.
- Four unit tests in `TestInstallOwnership` pin the contract: restoration reinstates the exact captured disposition, a nested install fails naming `restore()`, a released claim admits the next bracket, and a `restore()` with no claim is refused instead of installing a foreign handler.
- The session loop's `finally` migrated from raw `signal.signal(...)` to `guard.restore()` inside this same deliverable, and the then-dead `import signal` was pruned. The contract alone left eleven multi-command acceptance flows red: one memoized container keeps a single guard instance alive, so raw restoration latched the claim and the next in-process command's `install()` tripped the assertion. The leak was confirmed by a direct probe and reproduced under `-n0`, ruling out xdist worker reuse.
- Deliberate scope boundary: the transient press source is not reset here. `restore()` releases the claim but leaves `guard.source` set, so a later in-process bracket would name the previous key in its notice. Production is unaffected because every CLI invocation is a fresh process, and the seam deliverable clears press state at bracket entry with its own test.

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
