# Slice: Quit-Key Interrupt Latency
- **Status:** Completed
- **Milestone:** N/A (ad-hoc regression)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** [replica_interrupt_guard.py](/spikes/debug/quit-key-interrupt-latency/replica_interrupt_guard.py), [replica_interruptible_call.py](/spikes/debug/quit-key-interrupt-latency/replica_interruptible_call.py)
- **Component Docs:** [planning_service.md](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `quit-interrupt`

## Goal
Restore an instant quit on every platform. Pressing `q` during planning must interrupt within one poll interval instead of waiting for the remaining LLM response. This must hold on POSIX and on Windows, without a Windows-specific API.

## Context
- `ComponentName` `raise_interrupt` at `core/utils/interrupt_guard.py` called `signal.raise_signal`, which is thread-directed on POSIX, so the main thread ran the handler only at its next bytecode checkpoint. It now targets the main thread with `signal.pthread_kill` on POSIX and keeps the CRT raise on Windows.
- `ComponentName` `PlanningService.generate_plan` calls `get_completion` directly on the main thread. That call blocks in a raw socket read, which the Windows CRT raise cannot wake.
- `ComponentName` `generate_plan` reaches a second main-thread network read through `get_context_window` when the model-registry cache is cold or expired.
- `LibraryName` `litellm`: `get_completion` sends one non-streaming request and exposes no cancellation handle, so the quit path cannot abort it.
- The Remote Probe measured 0 ms wake-up of an unbounded `Future.result()` wait on both platforms (runs `39580764362` and `39581396641`).

## Scenarios
As a user, I want pressing `q` during planning to interrupt promptly so that I do not wait for an in-flight LLM response.

```gherkin
Given an interactive session on POSIX or Windows
When a planning completion is in flight and I press q
Then the interrupt notice appears within one poll interval
And the application exits
```

```gherkin
Given an interactive session
When a shell execution is in flight and I press q
Then the in-flight action drains and the remaining actions are skipped
```

## Edge Cases
- **POSIX blocked main thread**: If the main thread blocks in a call, then the handler runs at the next checkpoint, because `pthread_kill` targets the main thread directly.
- **Windows without pthread_kill**: If the platform is Windows, then delivery uses `signal.raise_signal`, because `os.kill` terminates the process there.
- **Worker exception**: If the wrapped callable raises, then the waiter raises the same exception, because the helper forwards every failure unchanged.
- **Process exit with a pending worker**: If the user quits during planning, then the daemon worker dies with the process, because a daemon thread does not block exit.
- **Hydration cache miss**: If the model-registry cache is cold or expired, then the wrapper spans hydration, because hydration calls `requests.get` on the main thread.

## Key Unknowns
- [x] `[Technical]` Windows wake-up for a raw socket read: cancellation was refuted in run `39579500381`; the resolution moves the call off the main thread, so no Windows primitive is needed.

## Impact
1. `[EXPAND]` `core/utils/interrupt_guard.py.raise_interrupt` — branch on platform while keeping the same signature.
2. `[NEW]` `core/utils/interruptible_call.py.run_interruptible` — add the daemon-worker helper.
3. `[MIGRATE]` `core/services/planning_service.py.generate_plan` — wrap the hydration, token-count, and completion phase.
4. `[MIGRATE]` `tests/suites/integration/core/services/test_quit_source_wiring.py` and `tests/suites/unit/adapters/outbound/test_terminal_quit_key_listener_reader.py` — observe the active POSIX primitive instead of `signal.raise_signal`.
5. `[NEW]` `tests/harness/setup/sigint_delivery.py.stub_sigint_delivery` — one shared seam stub that observes whichever delivery primitive is active, with its self-test at `tests/suites/unit/test_sigint_delivery_harness.py`.

No public port, DTO, or signature changes, so no breaking migration path is required.

## Deliverables
- [x] **Harness** - Add the shared `stub_sigint_delivery` seam to `tests/harness/setup/`, with its own harness unit test.
- [x] **Migration** - Move the three test seams onto the shared stub so delivery stays observable across the primitive change.
- [x] **Logic** - Deliver SIGINT to the main thread on POSIX in `raise_interrupt`, driven by unit tests.
- [x] **Logic** - Add the `run_interruptible` daemon-worker helper, driven by unit tests.
- [x] **Migration** - Wrap the planning hydration, telemetry, budget, and completion calls, with a test proving a quit during planning interrupts the wait.
- [x] **Cleanup** - Update the `raise_interrupt` docstring to describe POSIX main-thread delivery.

## Implementation Notes
The sandbox replicas at `spikes/debug/quit-key-interrupt-latency/replica_interrupt_guard.py` and `spikes/debug/quit-key-interrupt-latency/replica_interruptible_call.py` are the proven implementations. The composed MRE at `03-interruptible-planning-wait-mre.py` proves the topology across platforms.

The original deliverable order added a signature and failing coverage before any implementation, so it could not keep the suite green at every commit. The audit re-partitioned the work into six atomic deliverables. The shared seam stub lands first because it observes both the current `signal.raise_signal` path and the future `signal.pthread_kill` path, so the three test seams can migrate before delivery changes. The harness stub stubs `signal.pthread_kill` with `raising=False` only when the attribute exists, because Windows lacks it and the test process must not raise KeyboardInterrupt. No Wiring deliverable was added because the quit wiring already exists and its acceptance tracer bullet is shipped.

The Harness deliverable ships `stub_sigint_delivery(monkeypatch)` in `tests/harness/setup/sigint_delivery.py`. It patches `signal.raise_signal` unconditionally and patches `signal.pthread_kill` behind `hasattr` with `raising=False`, so the Windows leg never patches a missing attribute. Both primitives record into one shared list, so a test seam observes delivery whichever primitive the production code uses. Its self-test lives in `tests/suites/unit/test_sigint_delivery_harness.py`, following the repository precedent that harness boundary self-tests sit in `tests/suites/unit/`. The self-test passed in isolation and the full suite passed after the addition.

The Migration deliverable moves the three production test seams onto `stub_sigint_delivery`. `test_quit_source_wiring.py` and both the self-delivery and injected-hook seams in `test_terminal_quit_key_listener_reader.py` now call `stub_sigint_delivery(monkeypatch)` instead of patching `signal.raise_signal` directly, so delivery stays observable when `raise_interrupt` switches to `signal.pthread_kill` on POSIX. After the migration the only direct primitive patch in the suite lives inside the harness module itself, which is the source of the seam. The targeted run passed (`14 passed`), lint was clean, and the full suite passed (2025 passed, 5 skipped).

The POSIX delivery Logic deliverable changes `raise_interrupt` so delivery wakes the main thread instead of the calling thread. The helper now delivers with `signal.pthread_kill` to `threading.main_thread().ident` when the platform is not Windows and exposes the attribute, and it returns before the CRT path. Windows and any platform without `pthread_kill` keep `signal.raise_signal`, so the shipped quit notice stays intact there. The zero-argument signature is unchanged, so `container._record_quit_source` and `TerminalQuitKeyListener._trigger` needed no edits. Three new dispatch tests in `tests/suites/unit/core/utils/test_interrupt_guard.py` pin the contract: main-thread delivery on POSIX, main-thread targeting from a worker thread, and the CRT raise under a simulated Windows platform. The Red run reported `2 failed, 11 passed` with an empty recorder, and the Green run reported `13 passed` with clean lint. The full suite passed (2028 passed, 5 skipped). The branch matches the proven replica at `spikes/debug/quit-key-interrupt-latency/replica_interrupt_guard.py`. The stale docstring claim stays in place until the dedicated Cleanup deliverable.

The interruptible-call Logic deliverable adds `run_interruptible` in `src/teddy_executor/core/utils/interruptible_call.py`. The helper runs the callable on a daemon worker and polls the worker's future in short slices so a quit is handled promptly. The worker is a daemon, so a pending completion cannot block process exit after a quit. The worker catches `BaseException` and sets it on the future, so every failure reaches the waiter unchanged and the waiter never blocks forever. The helper imports `Callable` from `collections.abc`, which follows the codebase convention rather than the replica's `typing.Callable`. Five unit tests in `tests/suites/unit/core/utils/test_interruptible_call.py` pin result forwarding, off-thread execution, the daemon flag, ordinary exception forwarding, and `BaseException` forwarding. The Red run failed at collection with `ModuleNotFoundError`. The Green run reported `5 passed` after a trailing-newline fix, with clean lint and format checks. The full suite passed (2033 passed, 5 skipped). The helper stays unreferenced in `src/` until the planning migration deliverable adds its caller.

The planning-phase Migration deliverable consumes `run_interruptible` in `PlanningService.generate_plan`. The blocking phase moved into a private `_run_planning_phase` method, which performs hydration through `get_context_window`, the token count, telemetry, the budget check, and the completion in that order. `generate_plan` hands that method to `run_interruptible`, so the main thread waits on the worker's future instead of a raw socket read. The wrapper spans hydration and the budget check as well as the completion, because `get_context_window` is invoked three times in the phase and the off-thread test records the last invocation per seam. A nested closure initially tripped `PLR0915 Too many statements (43 > 40)` at `generate_plan`, so the phase was extracted to a method instead of suppressing the rule, which restores the statement budget and gives the phase a single responsibility. A refactor pass replaced the index-based tuple reorder with named unpacking. Two tests in `tests/suites/unit/core/services/test_planning_service.py` pin the contract. `test_planning_blocking_calls_run_off_the_calling_thread` records a worker identifier for `get_context_window`, `get_token_count`, and `get_completion`, and `test_quit_during_planning_interrupts_the_planning_wait` delivers a real quit through `raise_interrupt` while a fake completion blocks and asserts `KeyboardInterrupt` propagates, with a Windows skip because `pthread_kill` is absent there. The Red run reported the off-thread test failing on `context_window` with identical thread identifiers, and the composed quit test passed. The Green run reported `16 passed` for the planning module with clean lint and format. The full suite passed (2035 passed, 5 skipped). The zero-argument signatures and the `generate_plan` signature are unchanged.

The final Cleanup deliverable rewrites the `raise_interrupt` docstring in `src/teddy_executor/core/utils/interrupt_guard.py`. The old text claimed that `signal.raise_signal` reaches the handler from the main thread and from a reader thread on every platform, which was false after the POSIX main-thread switch. The new text states that POSIX targets the main thread through `signal.pthread_kill`, so delivery wakes a blocked main thread at its next checkpoint instead of waiting for the calling thread to return, and that Windows and any platform without `pthread_kill` keep the `signal.raise_signal` CRT raise path. The change touches prose only, so the behavioral contract stays pinned by `TestMainThreadDeliveryPrimitive`. The Red step confirmed the stale sentence present at line 134. The Green step confirmed the stale sentence gone, the new wording present, clean Ruff check and format, and a green interrupt-guard plus seam-harness run (`16 passed`). The full suite passed (2035 passed, 5 skipped). A Refactor review found nothing actionable, because the edit adds no helper, duplication, or shadow logic.

## Verification
1. **POSIX quit during planning:**
   Run `teddy start` in an interactive session, send a message, and press `q` while the agent responds.
   Verify the interrupt notice appears within one poll interval.
   Confirm the application exits.
2. **Execution quit:**
   Start a session with a long EXECUTE action and press `q`.
   Verify the in-flight action drains and the remaining actions are skipped.
3. **Windows quit during planning:**
   Repeat step 1 on Windows.
   Verify the interrupt notice appears within one poll interval rather than after the full LLM response.
