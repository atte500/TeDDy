# Slice: Quit-Key Interrupt Latency
- **Status:** Planned
- **Milestone:** N/A (ad-hoc regression)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** [replica_interrupt_guard.py](/spikes/debug/quit-key-interrupt-latency/replica_interrupt_guard.py), [replica_interruptible_call.py](/spikes/debug/quit-key-interrupt-latency/replica_interruptible_call.py)
- **Component Docs:** [planning_service.md](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `quit-interrupt`

## Goal
Restore an instant quit on every platform. Pressing `q` during planning must interrupt within one poll interval instead of waiting for the remaining LLM response. This must hold on POSIX and on Windows, without a Windows-specific API.

## Context
- `ComponentName` `raise_interrupt` at `core/utils/interrupt_guard.py` calls `signal.raise_signal`, which is thread-directed on POSIX. The main thread therefore runs the handler only at its next bytecode checkpoint.
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

No public port, DTO, or signature changes, so no breaking migration path is required.

## Deliverables
- [ ] **Contract** - Add the `run_interruptible` signature and the platform branching in `raise_interrupt`.
- [ ] **Harness** - Add unit coverage for the helper and for delivery while the main thread blocks.
- [ ] **Logic** - Implement the helper and the POSIX main-thread delivery.
- [ ] **Migration** - Wrap the planning phase and update the two stubbed test seams.
- [ ] **Cleanup** - Update the `raise_interrupt` docstring so it no longer claims prompt reader-thread delivery.

## Implementation Notes
The sandbox replicas at `spikes/debug/quit-key-interrupt-latency/replica_interrupt_guard.py` and `spikes/debug/quit-key-interrupt-latency/replica_interruptible_call.py` are the proven implementations. The composed MRE at `03-interruptible-planning-wait-mre.py` proves the topology across platforms.

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
