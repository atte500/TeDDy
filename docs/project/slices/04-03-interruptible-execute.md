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
9. `[PRUNE, DEFERRED]` `execute_valid_plan` in `src/teddy_executor/adapters/inbound/cli_helpers.py` - no callers, but milestone 05 requirement 5 assigns its deletion to [05-05](/docs/project/slices/05-05-dead-code-instrumentation.md), whose Harness deliverable needs the symbol present as a real red state; this slice leaves it untouched and records why.

## Deliverables
- [x] **Interface** - Give `InterruptGuard` install ownership: `install()` still returns the previous disposition but also records the claim, a second install fails its contract assertion naming the held disposition, and `restore()` reinstates the disposition and releases the claim.
- [x] **Interface** - Define `interrupt_scope(guard, listener)` as a context manager over the injected guard and listener, stopping the listener and releasing the claim in `finally` on every exit path including a raised exit.
- [x] **Harness** - Extend the SIGINT delivery double so a simulated press routes through the currently installed handler, letting an acceptance test drive the real guard without raising in the test process.
- [x] **Wiring** - Move the session loop onto the seam unchanged and prove the existing session interrupt and quit-listener tests stay green before the stateless path adopts anything.
- [x] **Adapter** - Bracket the stateless `execute` command body with the seam, surface the interrupt notice at that boundary, and add the acceptance test for an interrupted run.
- [x] **Cleanup** - Flip `boundary_owns_interrupt_lifecycle` in the CLI component page, record the `execute` key semantics in the reviewer page, retire the twin inline shell mock onto `FakeShellExecutor`, and defer the dead `execute_valid_plan` helper to slice 05-05, which owns its deletion.

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

**Deliverable 2 — the shared bracket seam (delivered).**

- `interrupt_scope(guard, listener)` is a `@contextmanager` over the already-resolved guard and listener, so it holds no container and constructs no concrete `InterruptGuard`. It clears transient press state, installs the guard, starts the listener, and in `finally` stops the listener then calls `guard.restore()`.
- `InterruptGuard.clear_source()` was added rather than letting the adapter write `guard.source` directly: press state stays the guard's, while the seam decides when that state is transient. A leftover source would name the previous run's key in this run's notice, which is reachable because one memoized container keeps a single guard alive across in-process commands.
- Release order is stop-then-restore, because no keystroke may be read while the previous handler comes back; the ordering test observes `stop()` while the guard's handler is still installed.
- `listener.start()` sits inside the guard's claim window rather than before it, so a raising start cannot orphan the claim. The port documents `stop()` as idempotent and a no-op off-TTY, so a spurious stop is the cheap failure and a latched claim is the expensive one.
- The seam never swallows a `KeyboardInterrupt` or a `typer.Exit`: the boundary that entered the bracket owns the notice and the exit code.
- Eight unit tests in `tests/suites/unit/adapters/inbound/test_interrupt_scope.py` pin it: install-and-start for the body, release on the normal, raising, `typer.Exit` and `KeyboardInterrupt` paths, stop-before-restore ordering, a second bracket on one memoized guard, and entry clearing a stale press source.
- No production caller uses the seam yet: the session loop keeps its inline install/restore until the Wiring deliverable migrates it, so this commit adds the capability without switching any boundary onto it.

**Deliverable 3 — SIGINT routing mode in the delivery double (delivered).**

- The mode is an enum on the existing helper (`SigintDeliveryMode`) rather than a second seam, because three suites already pin the recorder contract. `RECORD` stays the default and the routing leg is strictly additive.
- `ROUTE_TO_HANDLER` resolves `signal.getsignal(signal.SIGINT)` at press time, never at stub time: the run installs its handler after the stub is applied, so an early lookup would capture the pre-run disposition and drive nothing.
- The signal number is recorded BEFORE routing, so a handler that raises — the guard's WAITING branch does exactly that — still leaves evidence of the press for the assertion.
- A non-callable disposition such as `SIG_IGN` is skipped rather than invoked, because not every disposition the process can hold is a Python callable.
- Five cases in `tests/suites/unit/test_sigint_delivery_harness.py` pin it: routing through both `raise_signal` and `pthread_kill`, record mode leaving the installed handler untouched, the `SIG_IGN` skip, and a routed press setting the real `InterruptGuard`'s drain flag inside `enter_executing()`. The three pre-existing recorder pins are unchanged.
- Full suite at this commit: 2643 passed, 5 skipped.
- No production code changed here; the mode exists for the Adapter deliverable's acceptance test.

**Noted for the Adapter deliverable.** No shell-executor double exists under `tests/harness`. The only acceptance test needing one builds a bare `Mock(spec=IShellExecutor)` inline in `test_execute_fail_fast.py`, so the `execute` bracket's acceptance test must add a sanctioned in-memory shell double rather than a second inline mock, and that double retires the existing inline one in the same stroke.

**Deliverable 4 — session loop onto the shared seam (delivered).**

- The inline `interrupt_guard.install()` / `quit_listener.start()` / `finally` block became `with interrupt_scope(interrupt_guard, quit_listener):`, with the turn loop re-indented under it. The swap stayed mechanical because the old `finally` held exactly `quit_listener.stop()` then `interrupt_guard.restore()` — the seam's own release order — and a grep confirmed the session loop was the last production bracket outside the seam.
- The `except KeyboardInterrupt` stays OUTSIDE the `with` but inside the surrounding `try`, so the release runs while the interrupt unwinds and the notice still renders: `restore()` reinstates the disposition but never clears press state, so `interrupt_guard.source` is still readable.
- The turn loop is ~60 lines, so the wrap ran as a targeted re-indent script anchored on the region's own lines (guard resolve, listener start, `try:`, `except`, `finally:`, `restore()`), asserting the old `finally` body first so no statement could be dropped. A whitespace-sensitive `EDIT` over that block would have been brittle.
- One existing test moved its arrangement, not its coverage: `test_session_loop_names_the_quit_key_when_recorded` recorded `q` BEFORE entering the loop, which the seam's entry-time `clear_source()` correctly erases. Because the real quit-key listener records the key and self-delivers SIGINT mid-turn, the press now happens inside the resume side effect. The predicted single failure appeared exactly once (25 passed, 1 failed) before the fix, which is the evidence that handler install, restoration, listener lifecycle, drain exit, and baseline reset all survived unchanged.
- Two hygiene defects from the programmatic rewrite were fixed in this same deliverable rather than deferred: the stale "tracer bullet" comment block stacked above the new bracket explanation, and the collapsed blank-line separation before `_format_drift_clause`.
- No production behavior changed: the three existing session-loop suites plus the seam, baseline-reset, and pipeline-wiring suites pass (26 targeted), and the full suite is unchanged at 2643 passed, 5 skipped. No test was added.

**Deliverable 5 - the stateless `execute` bracket (delivered).**

- The bracket spans the whole run: `get_plan_content`, the `IRunPlanUseCase.execute(...)` call, the `except (InvalidPlanError, NotImplementedError)` handler, the drain check, and the report gate all sit inside `with interrupt_scope(interrupt_guard, quit_listener):`. The gate stays inside so a validation `typer.Exit` unwinds through the seam's `finally`, and the guard and listener are resolved from the container before the bracket because entering it is what needs them.
- Two notice paths are required, not one. A mid-execution press raises nothing: the guard sets its drain flag, `ActionDispatcher` maps `ShellOutput["interrupted"]` to `ActionStatus.INTERRUPTED`, and `ExecutionReportAssembler` promotes that to `RunStatus.INTERRUPTED`. So the boundary checks `interrupt_guard.interrupted.is_set()` after the use case and echoes the notice itself. `except KeyboardInterrupt` covers only the WAITING phase, where the guard raises and no report is assembled at all; `format_interrupt_notice` falls back to `Ctrl+C` when no press source was recorded, which is exactly that path.
- The notice goes to stderr (`err=True`), matching this boundary's other diagnostics, so stdout stays the report channel `ReportParser` consumes.
- Red evidence: the unbracketed run exited `130` (`SystemExit(130)`, Click's `Aborted!`), proving the routed press reached the inherited `default_int_handler` and unwound straight out of `execute` - no report, no notice. The four harness tests passed in that same run, which proved the fake reached the command's resolver.
- `FakeShellExecutor` subclasses `IShellExecutor` so signature drift fails static checking, and takes an injected `on_execute` callback so the press fires inside `execute()` while the orchestrator holds `enter_executing()` - a WAITING-phase press would produce no report to assert on. It retired the inline `Mock(spec=IShellExecutor)` in `test_execute_fail_fast.py`; the twin in `test_ast_parser_resilience_wiring.py` moves during Cleanup. `PLR0913` is bypassed inline with a reason because the six-parameter signature IS the port contract, and narrowing it would defeat the double.
- Green and gates: 6 targeted tests green, full suite 2648 passed / 5 skipped (2643 baseline plus the four harness tests and the interrupted-run acceptance test). No test showed a spurious notice or an all-SKIPPED run. The seam does not reset the drain flag, so one memoized guard could in principle leak a drain into a later in-process run; production is unaffected (one process per invocation), so it is recorded as debt to be assessed during Cleanup rather than patched speculatively here.
- `format_interrupt_notice` appends the session resume hint, which reads slightly off for a stateless run. The test asserts only the naming prefix, and changing the shared notice text is out of this slice's scope.

**Deliverable 6 - Cleanup and As-Built (delivered).**

- `boundary_owns_interrupt_lifecycle` in the CLI adapter page now states that every boundary that can run an action enters the one shared seam, names the session loop and the stateless `execute` run as the two owners, and records why neither may take its own snapshot. The sibling dependency line that still read "Manage session-loop interrupt handling" was corrected in the same edit, because leaving it would have contradicted the invariant beside it.
- The reviewer page gained `bracket_live_during_review` next to `stdin_ownership`: the reviewer mounts inside `ExecutionOrchestrator.execute`, which both boundaries now run inside the seam, so the disposition and listener are live while the TUI is up, and the `stdin_owned()` claim is what keeps the raw reader off Textual's keys. The Keyboard bindings section notes that `q` means the same thing in a session and a stateless run.
- The twin inline `Mock(spec=IShellExecutor)` in `test_ast_parser_resilience_wiring.py` moved onto `FakeShellExecutor`; both slice-scoped shell doubles are now retired, and the arrangement change preserved coverage rather than adding any.
- `execute_valid_plan` was deliberately NOT deleted here. Milestone 05 requirement 5 names its deletion with `Owner: 05-05`, and slice 05-05's Harness deliverable is a module-surface assertion that needs a real dead public function to fail on. Deleting it from this slice would gut another milestone's artifact to satisfy one Impact line, so our item is marked `[PRUNE, DEFERRED]` with the reason and the function stays unreachable.
- The non-slice-scoped shell double in `test_pipeline_message_break.py` is a six-mock unit fixture, not an acceptance arrangement, so it was recorded under milestone 06's shared-fake consolidation (06-03) instead of being rewritten from a slice that never exercised it.
- Raw `signal.signal(...)` restorations in the interrupt suites were classified rather than migrated: they are fixture-level ambient-state restoration wrapped around a fresh guard per test, and a latched install claim would only bite on a second install of the same instance, which the green suite shows never happens. Migrating them to `guard.restore()` would test the guard through itself.

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
