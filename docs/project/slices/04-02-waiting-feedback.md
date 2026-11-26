# Slice: Waiting Feedback for Agent Response
- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** [`spikes/prototypes/waiting-indicator/preview.py`](/spikes/prototypes/waiting-indicator/preview.py)
- **Component Docs:** [ConsoleInteractor](/docs/architecture/adapters/outbound/console_interactor.md), [PlanningService](/docs/architecture/core/services/planning_service.md), [IUserInteractor](/docs/architecture/core/ports/outbound/user_interactor.md)
- **Scope Slug:** `waiting-feedback`

## Goal
A user waiting on a slow — often local — model sees one frozen line and cannot tell a long generation from a hung process. Render an animated indicator for exactly the duration of the model call so the process visibly stays alive, without touching the plan-validation contract.

## Context
- `PlanningService.generate_plan`: Prints one static `[{turn}] {session} | Waiting for {agent} to respond...` line through `IUserInteractor.display_message`, then runs preflight, context assembly, and the generation phase. Nothing else is printed until the plan arrives.
- `PlanningService._run_planning_phase`: Runs on `run_interruptible`'s daemon worker. It hydrates, counts tokens, prints telemetry through four `display_message` calls, checks the budget, then delegates the completion to `_perform_generation_with_retry`. Telemetry already prints from a worker thread, so worker-thread UI calls are established practice.
- `PlanningService._perform_generation_with_retry`: The only region that is purely waiting — the retry loop around `get_completion`. Bracket this loop and the indicator covers the model call and nothing else.
- `spikes/prototypes/waiting-indicator/preview.py`: The look-alike prototype settled the appearance. The chosen variant renders a bare braille-dot spinner on its own transient line beneath the telemetry, with no label and no elapsed suffix, and erases it on completion so the settled layout stays byte-identical to today.
- **Layout invariant:** The indicator owns one transient line beneath the telemetry and never rewrites a line it did not print, so the waiting banner, the model/context/session-cost block, and the plan summary render byte-identically to today. The feature is invisible whenever it is not animating.
- **Input invariant:** The indicator reads no stdin, installs no signal handler, and never blocks, because `run_interruptible` polls its future every 50 ms on the main thread and that poll is what delivers `q` and Ctrl+C within one slice.
- `run_interruptible` (`core/utils/interruptible_call.py`): Runs the callable on a daemon worker and polls the future every 50 ms on the calling thread, so a quit handler runs within one slice.
- `IUserInteractor`: Exposes no progress or activity hook. `display_message` is a whole-line `Rich` print, so an in-place animation cannot ride on it.
- `ConsoleInteractorAdapter`: Constructs its `Console` with `stderr=True` and already branches on `self._console.is_terminal` when it renders anything richer than a plain echo.
- `rich` (external): `rich>=15.0.0,<16` is a declared dependency and ships `rich.live.Live`, which hosts a transient region with its own refresh timer.
- Test harness: `TestEnvironment` resolves `IUserInteractor` as an auto-specced mock and `_apply_interactor_defaults` registers behaviour per method. An auto-specced mock tolerates an unspecified method, so the new port methods cannot break harness flows, but explicit defaults keep the call sequence assertable.

## Scenarios

> As a user waiting on a slow model, I want a visible sign of activity so that I do not mistake a long generation for a hang.

```gherkin
Given a terminal session and a model that takes a long time to answer
When the plan is being generated
Then an animated indicator is visible for the duration of the model call
And it is gone before the plan is presented
```

> As a user running TeDDy in a script, I want the log to stay machine-readable.

```gherkin
Given stderr is not a terminal
When the plan is being generated
Then no animation is rendered and every line stays newline-delimited
```

> As a user whose request fails, I want the failure reported on a clean line.

```gherkin
Given the model call raises a TeddyError
When the wait ends
Then the indicator is already stopped and the error text prints without animation residue
```

## Edge Cases
- **Non-terminal stderr**: If the console is not a terminal, then both methods are no-ops, because animation control characters corrupt redirected logs and CI transcripts.
- **Unbalanced end**: If `end_waiting` runs with no active region, then it does nothing, because a defensive `finally` may end a region a failure already ended.
- **Nested begin**: If `begin_waiting` runs while a region is active, then the label is replaced without stacking a second region, because only one line may be owned at a time.
- **Very fast response**: If the completion returns before the first refresh, then the region erases itself on stop, because transient rendering must leave no residue above the telemetry.
- **Exception inside the region**: If the completion raises, then the region stops before the error propagates, because the traceback must not interleave with the animation.
- **Retry notice**: If an empty response triggers a retry, then the notice prints on its own line and the indicator resumes, because the user must be able to read both.
- **Interrupt during the wait**: If `q` or Ctrl+C interrupts the wait, then the region stops as the turn unwinds, because the cursor must not stay hidden.
- **Two waiting seams**: `InterruptGuard.enter_waiting` exists in `core/utils/interrupt_guard.py` with a dedicated unit test and zero production call sites, while this slice adds `begin_waiting` to the interactor. The guard is a process-global: `container.py` registers it as a singleton owning the SIGINT disposition, `session_cli_handlers.py` resolves it at the CLI boundary, and `container.py:269` passes it into the session orchestration. It never reaches `PlanningService`, and threading a process-global signal owner into a core service would break the constructor-injection law, so the animation starts and stops without it: this slice deletes `enter_waiting` and its dedicated test as a port contraction. A second seam with no caller is debt rather than design, and the guard's EXECUTING/WAITING phase stays where it is — the CLI boundary it already owns.
- **Abandoned region at exit**: If the process exits while the region is still open on the daemon worker, then an interpreter-exit hook stops it, because a daemon thread abandoned by a quit never runs its own `finally` and a hidden cursor would outlive the process.
- **Label wider than the console**: If the label exceeds the width, then it wraps or truncates inside the region, because the animation must never break the layout.
- **Non-streaming model**: If the provider answers in one shot, then the indicator still appears and still stops on completion, because the region tracks the wait, not the transport.

## Key Unknowns
- None. The look-alike prototype at [`spikes/prototypes/waiting-indicator/preview.py`](/spikes/prototypes/waiting-indicator/preview.py) settled the appearance: a bare braille-dot spinner on a transient line beneath the telemetry, no label and no elapsed suffix, erased on completion. The two-method port holds, because the design needs no live figure from the core.

## Impact
1. `[EXTEND]` `IUserInteractor.begin_waiting` / `IUserInteractor.end_waiting` — Additive operations carrying silent no-op default bodies, so the one concrete implementation stays instantiable. The harness resolves the port as an auto-specced mock, so no caller breaks.
2. `[NEW]` `adapters/outbound/console_waiting_indicator.py` — A `WaitingIndicator` owning the stderr `Rich` live region, its terminal gate, and its teardown.
3. `[MIGRATE]` `ConsoleInteractorAdapter` — Implement both methods by delegating to the indicator.
4. `[MIGRATE]` `PlanningService._perform_generation_with_retry` — Bracket the retry loop with `begin_waiting` and a `finally`-guarded `end_waiting`, naming the responding agent in the label.
5. `[MIGRATE]` `TestEnvironment._apply_interactor_defaults` — Register deterministic defaults for both methods.
6. `[MIGRATE]` `docs/architecture/adapters/outbound/console_interactor.md` and `docs/architecture/core/services/planning_service.md` — Document the two operations and the bracketing boundary.
7. `[PRUNE]` `InterruptGuard.enter_waiting` (`src/teddy_executor/core/utils/interrupt_guard.py`) — deleted with its dedicated unit test, because the guard is a CLI-boundary process-global that `PlanningService` never receives.

## Deliverables
- [x] **Interface** — Add `begin_waiting(message: str)` and `end_waiting()` to `IUserInteractor` with contract docs pinning that they are display-only, must never raise, must tolerate an unbalanced `end_waiting`, are no-ops without an attached terminal, never alter a line they did not print, and never touch stdin or a signal handler.
- [ ] **Harness** — Register recording no-op defaults for both methods in `TestEnvironment._apply_interactor_defaults` so harness-driven planning flows stay deterministic and the call sequence is assertable.
- [ ] **Wiring** — Call `begin_waiting` before the retry loop and `end_waiting` in a `finally` inside `PlanningService._perform_generation_with_retry`, then extend the planning-service unit coverage to assert the begin/end order around a stubbed completion. Delete `InterruptGuard.enter_waiting` and its dedicated test in the same change, because the guard is a CLI-boundary process-global that never reaches `PlanningService`.
- [ ] **Adapter** — Implement `WaitingIndicator` in `adapters/outbound/console_waiting_indicator.py` and delegate both `ConsoleInteractorAdapter` methods to it, with unit tests covering the terminal gate, unbalanced end, nested begin, exception unwinding, interrupt teardown, and the interpreter-exit hook that stops a region abandoned on the daemon worker.
- [ ] **Cleanup** — Update the `ConsoleInteractor` and `PlanningService` component docs, add the slice to the Milestone 4 delivered list, and remove this slice's Key Unknown once the prototype answers it.

## Implementation Notes

### Interface — delivered

The port declares `begin_waiting(message)` and `end_waiting()` as **concrete no-op defaults**, superseding this slice's original "additive abstract methods" wording. `ConsoleInteractorAdapter` is the sole `src/` implementation and the real container resolves it across the acceptance suite, so an `@abstractmethod` addition would have made it uninstantiable between this commit and the Adapter deliverable and turned the whole suite red. Concrete bodies keep the extension additive by construction, and `test_waiting_operations_are_not_abstract` pins that property so a later abstract-ization is caught instead of silently breaking adapters.

Contract coverage lives at `tests/suites/unit/core/ports/outbound/test_user_interactor_contract.py` (8 tests): both operations exist, the signatures are `(self, message)` and `(self)`, neither is abstract, both default bodies emit no bytes, and repeated or unbalanced calls stay silent. Two consequences carry forward:
- `test_waiting_operations_are_display_only` inspects each method's source, so neither docstring may contain the lowercase substring `signal` or the literal `input(`. The contract is phrased as "read stdin" and "process-interrupt handler" instead.
- The silence assertions drive the base bodies unbound (`IUserInteractor.begin_waiting(None, ...)`), so the default bodies must stay stateless.

**Label reconciliation.** The Key Unknowns record a *bare* glyph with no label, while the Edge Cases carry a "label wider than the console" behaviour and the pinned signature takes `message`. A bare glyph would leave the parameter dead and that edge case untestable, so the Adapter deliverable renders `{spinner} {message}` on the transient line and the core supplies the short label `Waiting for {agent} to respond...` — the banner's wording without duplicating its turn/session prefix. Both statements then hold: the indicator rewrites no line it did not print, and the label has a defined width behaviour.

**Prune plan confirmed by census.** `InterruptGuard.enter_waiting` has zero production call sites and exactly two test-side users: the dedicated case in `tests/suites/unit/core/utils/test_interrupt_guard.py` (deleted with the method) and `tests/suites/unit/core/utils/test_interruptible_call.py`, which wraps `run_interruptible` in it purely as phase bookkeeping. The guard's default phase already *is* WAITING — a signal raises immediately before any phase is entered — so that wrapper is redundant and is dropped rather than migrated.

## Verification
1. **Terminal animation:**
   Run `uv run teddy start -m "plan a small refactor"` against a slow or local model.
   Confirm the indicator animates from the start of the generation until the plan appears, leaving no residue above the telemetry.
2. **Non-terminal output:**
   Run `uv run teddy start -m "plan a small refactor" > out.log 2>&1`.
   Confirm `out.log` contains no carriage returns and no spinner frames.
3. **Failure path:**
   Point `llm.api_base` at an unreachable endpoint.
   Confirm the indicator stops before the error message prints.
4. **Interrupt path:**
   Start a long generation and press `q`.
   Confirm the cursor is visible and the shell prompt is clean.
