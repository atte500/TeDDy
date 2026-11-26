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
- [x] **Harness** — Register recording no-op defaults for both methods in `TestEnvironment._apply_interactor_defaults` so harness-driven planning flows stay deterministic and the call sequence is assertable.
- [x] **Wiring** — Call `begin_waiting` before the retry loop and `end_waiting` in a `finally` inside `PlanningService._perform_generation_with_retry`, then extend the planning-service unit coverage to assert the begin/end order around a stubbed completion. Delete `InterruptGuard.enter_waiting` and its dedicated test in the same change, because the guard is a CLI-boundary process-global that never reaches `PlanningService`.
- [x] **Adapter** — Implement `WaitingIndicator` in `adapters/outbound/console_waiting_indicator.py` and delegate both `ConsoleInteractorAdapter` methods to it, with unit tests covering the terminal gate, unbalanced end, nested begin, exception unwinding, interrupt teardown, and the interpreter-exit hook that stops a region abandoned on the daemon worker.
- [ ] **Cleanup** — Update the `ConsoleInteractor` and `PlanningService` component docs, add the slice to the Milestone 4 delivered list, and remove this slice's Key Unknown once the prototype answers it.

## Implementation Notes

### Interface — delivered

The port declares `begin_waiting(message)` and `end_waiting()` as **concrete no-op defaults**, superseding this slice's original "additive abstract methods" wording. `ConsoleInteractorAdapter` is the sole `src/` implementation and the real container resolves it across the acceptance suite, so an `@abstractmethod` addition would have made it uninstantiable between this commit and the Adapter deliverable and turned the whole suite red. Concrete bodies keep the extension additive by construction, and `test_waiting_operations_are_not_abstract` pins that property so a later abstract-ization is caught instead of silently breaking adapters.

Contract coverage lives at `tests/suites/unit/core/ports/outbound/test_user_interactor_contract.py` (8 tests): both operations exist, the signatures are `(self, message)` and `(self)`, neither is abstract, both default bodies emit no bytes, and repeated or unbalanced calls stay silent. Two consequences carry forward:
- `test_waiting_operations_are_display_only` inspects each method's source, so neither docstring may contain the lowercase substring `signal` or the literal `input(`. The contract is phrased as "read stdin" and "process-interrupt handler" instead.
- The silence assertions drive the base bodies unbound (`IUserInteractor.begin_waiting(None, ...)`), so the default bodies must stay stateless.

**Label reconciliation.** The Key Unknowns record a *bare* glyph with no label, while the Edge Cases carry a "label wider than the console" behaviour and the pinned signature takes `message`. A bare glyph would leave the parameter dead and that edge case untestable, so the Adapter deliverable renders `{spinner} {message}` on the transient line and the core supplies the short label `Waiting for {agent} to respond...` — the banner's wording without duplicating its turn/session prefix. Both statements then hold: the indicator rewrites no line it did not print, and the label has a defined width behaviour.

**Prune plan confirmed by census.** `InterruptGuard.enter_waiting` has zero production call sites and exactly two test-side users: the dedicated case in `tests/suites/unit/core/utils/test_interrupt_guard.py` (deleted with the method) and `tests/suites/unit/core/utils/test_interruptible_call.py`, which wraps `run_interruptible` in it purely as phase bookkeeping. The guard's default phase already *is* WAITING — a signal raises immediately before any phase is entered — so that wrapper is redundant and is dropped rather than migrated.

### Harness — delivered

`TestEnvironment._apply_interactor_defaults` now registers `begin_waiting` and `end_waiting` with `return_value = None`, alongside the three existing interactor defaults. Coverage lives at `tests/suites/unit/test_user_interactor_harness.py` (2 tests) and drives the double through the composition `env` fixture, so it asserts against the same configured interactor every planning and acceptance flow receives.

The registration fixes a real unfaithfulness rather than a cosmetic one. The harness double is a `POSIXPathMock(spec=IUserInteractor)`, and an auto-specced double answers an *unregistered* operation with a truthy dynamic child mock — the Red run printed `assert <POSIXPathMock name='mock.begin_waiting()' ...> is None`. The port's contract is `None`, so before this change a harness-driven planning flow observed a fabricated answer. The rule generalizes: any port operation whose contract is "returns None" needs that `None` registered explicitly in the harness, because the mock's default answer is never `None`. Calls stay recorded either way, which is what keeps the upcoming bracketing order assertable from the double.

Full suite after the change: 2636 passed, 5 skipped — the previous 2634 plus exactly the two new tests, so no fixture-consuming suite was disturbed.

### Wiring — delivered

`PlanningService._perform_generation_with_retry` now brackets its **entire** retry loop with `begin_waiting` and a `finally`-guarded `end_waiting`, and the responding persona's name reaches it as a keyword-only `agent_name` threaded `generate_plan` → `_run_planning_phase` → `_perform_generation_with_retry`. Coverage lives at `tests/suites/unit/core/services/test_planning_service_waiting.py` (4 tests): the begin-before/completion/end-after ordering, the label naming the agent, unwinding when the completion raises, and one region spanning a retry.

Three decisions carry the behaviour:
- **One region spans every attempt.** Bracketing the loop rather than each attempt is what satisfies the retry-notice edge case: the notice prints on its own line while the region stays open, so the user can read both, and the indicator never flickers between attempts. The `finally` erases the region before a raising completion propagates, so a traceback cannot interleave with the animation.
- **The wording has one source.** A module-level `waiting_label(agent_name)` returns `Waiting for {agent} to respond...` and both the waiting banner and the transient line render it. The banner's bytes are unchanged, so no acceptance assertion moved — shadow logic is eliminated forward rather than in a later refactor.
- **The prune dropped no coverage.** `InterruptGuard.enter_waiting` is deleted along with its dedicated case in `test_interrupt_guard.py` and the now-redundant wrapper in `test_interruptible_call.py` (the census held: zero production callers, exactly two test-side users). The deleted test asserted "a signal in WAITING raises immediately", which `test_default_phase_signal_raises_keyboard_interrupt` already pins — the guard's default phase *is* WAITING — so pruning a superseded test removed no invariant.

`agent_name` is keyword-only on both new parameters, so the three existing retry call sites in `test_planning_service_retries.py` had to be migrated explicitly instead of silently absorbing a concrete default that constructor-injection purity forbids.

Full suite after the change: 2639 passed, 5 skipped — the previous 2636, minus the one pruned guard case, plus exactly the four new waiting tests.

### Adapter — delivered

`adapters/outbound/console_waiting_indicator.py` owns the one transient line. `WaitingIndicator(console, live_factory, exit_hooks)` gates on the *injected* console's `is_terminal`, opens the region its factory builds, renders `{glyph} {message}` on a callable the region re-invokes, and erases it on `end`. The glyph advances from an internal frame counter, so successive refreshes animate without a clock entering any assertion. `create_live` takes an explicit `live_class`, and `create_indicator(console)` is the one place `rich.live.Live` and `atexit` are bound.

Three rich realities became code rather than commentary:
- **Redirection is off explicitly.** `Live.start` calls `_enable_redirect_io()` before its screen branch, so the production factory passes `redirect_stdout=False, redirect_stderr=False`; the defaults would swap the process-global streams from the daemon worker.
- **A non-terminal console never starts a region**, because `Live.stop()` renders. That gate is what keeps redirected logs and CI transcripts newline-delimited.
- **One exit hook per wait.** `rich.live` registers none, so a region abandoned by a killed daemon worker would leave the cursor hidden. The hook is registered with `begin` and forgotten before `stop`.

`ConsoleInteractorAdapter` gained an optional `waiting_indicator` mirroring its existing optional `console`, defaulting to `create_indicator(self._console)`. Production therefore needs no container change — `registries/infrastructure.py:128` is untouched — and every existing construction site stays valid; both new operations claim no stdin, which the untouched `stdin_ownership` suite confirms.

**Never-raise guards.** Red first: `2 failed, 10 passed`, with `OSError: terminal went away` propagating out of `begin()` and out of `_teardown()` → `live.stop()`. Both guards now log the error text through `logger.warning`, since the architecture forbids silent suppression and the tests assert the message. The release order in `_teardown` is deliberate — clear `_live`, unregister the hook, then stop — so a failing stop strands nothing and a repeated `end()` stays silent. A failed `start` issues no `stop`, because rich tears a partially started region down itself before re-raising.

**Suppression hygiene.** `select = ["F", "E", "W", "C901", "PLR", "TID"]`, so `BLE001` never fires: the `# noqa: BLE001` written alongside the guard was inert and was removed, keeping its reason comment. Ruff reports clean with and without it.

**Real-region integration.** `tests/suites/integration/adapters/outbound/test_console_waiting_indicator_live.py` (2 tests) binds `create_indicator` to rich's own `Live` on an isolated `StringIO` console with `force_terminal=True, width=80`. The label and a spinner glyph are genuinely drawn, the region reopens after teardown, and `sys.stdout`/`sys.stderr` are the identical objects afterwards — the last of which no double can prove.

**Refactor in the same commit.** `_failing_indicator` had manufactured a second, unwired `RecordingExitHooks`, and the guard tests compensated by reading `indicator._exit_hooks`; it now binds the registry once and returns it, so the assertions observe the collaborator they name.

Test census: 16 new cases — 10 indicator unit, 2 never-raise unit, 2 delegation unit, 2 real-region integration. Full suite after the change: 2655 passed, 5 skipped (the 2639 baseline plus 16).

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
