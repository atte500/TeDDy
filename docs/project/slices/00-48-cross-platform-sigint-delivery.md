# Slice: Cross-Platform SIGINT Self-Delivery
- **Status:** Planned
- **Milestone:** N/A (ad-hoc bug fix)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** [Windows quit-notice suppression case file](/docs/project/debugging/47-windows-quit-notice-suppression.md)
- **Component Docs:** N/A (the interrupt guard has no component design document)
- **Scope Slug:** `sigint-delivery`

## Goal
Pressing the bare `q` key on Windows must print the interrupt notice and preserve the turn report. The self-delivery primitive must reach the Python SIGINT handler on every platform.

## Context
Key findings from the resolved case file and static code reading.
- `InterruptGuard` (`src/teddy_executor/core/utils/interrupt_guard.py`): installs the process SIGINT handler and records the pressed key. The contract expects delivery to reach `_handle_signal`.
- `container._record_quit_source` (`src/teddy_executor/container.py:47`): records `"q"` on the shared guard, then calls `os.kill(os.getpid(), signal.SIGINT)`.
- `TerminalQuitKeyListener._trigger` (`src/teddy_executor/adapters/outbound/terminal_quit_key_listener.py:157`): the default no-hook branch calls `os.kill(os.getpid(), signal.SIGINT)`.
- CPython: on Windows `os.kill` calls `TerminateProcess` for every signal except `CTRL_C_EVENT` and `CTRL_BREAK_EVENT`. `signal.raise_signal(signal.SIGINT)` uses the CRT raise path and reaches the Python handler from the main thread and from a reader thread.
- Empirical proof: Remote Windows Probe run `39247429235` showed production `rc=2` and silent while the `signal.raise_signal` replica printed the notice with `rc=0`, in direct and threaded modes. The local Darwin control was green in all four scenarios.
- Test seams pinning the delivery tuple: `tests/suites/integration/core/services/test_quit_source_wiring.py`, `tests/suites/unit/adapters/outbound/test_terminal_quit_key_listener_reader.py`, and `tests/suites/unit/core/utils/test_interrupt_guard.py` with its real-delivery class skipped on Windows.
- No Wiring deliverable is required. The composition root and listener boundaries already exist, and the Windows scenario cannot run in local CI. The resolved case file's remote probe is the acceptance evidence for the Windows scenario.
- No port signature and no data contract changes. The steps are additive and non-breaking.

## Scenarios

> As a TeDDy user on Windows, I want pressing `q` to interrupt the current action gracefully so the audit trail survives.

```gherkin
Given a TeDDy session is executing an action on Windows
When I press the bare `q` key
Then the process must print "Interrupted by user (q). To continue the session, use `teddy resume`."
And the turn report must be written
And the process must exit with code 0
```

```gherkin
Given a TeDDy session is executing an action on POSIX
When I press the bare `q` key
Then the interrupt notice must still print and the report must still be written
```

```gherkin
Given the quit-key listener is constructed with an injected `on_quit` hook
When the quit key is detected
Then the injected hook must run and no SIGINT must be self-delivered
```

## Edge Cases
- **Reader-thread delivery**: If the quit key is read on a worker thread, then the helper must still reach the guard handler, because signal handlers run in the main thread and `signal.raise_signal` uses the process-level CRT path. Verified by the remote probe.
- **Guard installed and WAITING**: If delivery occurs outside an EXECUTING window, then the guard raises `KeyboardInterrupt` immediately, because nothing is in flight. Seam tests must avoid accidental termination.
- **Injected hook path**: If `on_quit` is provided, then the listener must not self-deliver SIGINT, because the injected hook owns the reaction.
- **Grace-window semantics**: If a second signal arrives during EXECUTING, then escalation behavior must stay unchanged, because the helper only replaces the delivery primitive.
- **No existing helper**: If a module-level helper already existed, then the slice would migrate to it instead of creating one. Discovery showed none.

## Key Unknowns
None. The root cause is resolved and empirically verified by the Remote Windows Probe. Prerequisite slices are not applicable.

## Impact
1. `[EXPAND]` `interrupt_guard.raise_interrupt` — add a module-level delivery helper beside the guard contract that consumes it.
2. `[MIGRATE]` `container._record_quit_source` — replace `os.kill` with the shared helper.
3. `[MIGRATE]` `TerminalQuitKeyListener._trigger` — replace `os.kill` with the shared helper.
4. `[CONTRACT]` `os.kill` self-delivery sites — remove the obsolete delivery calls once both consumers migrate.

## Deliverables
- [ ] **Logic** — Add the module-level `raise_interrupt()` helper beside `InterruptGuard` and drive real SIGINT delivery through the guard handler in the guard Unit suite. Remove the Windows skip where real delivery is now safe.
- [ ] **Migration** — Route the composition-root quit recorder through `raise_interrupt()` and align its integration seam so the shared guard observes the recorded key without terminating the test process.
- [ ] **Migration** — Route the listener's default self-delivery branch through `raise_interrupt()` and align the reader Unit seam.

## Implementation Notes

## Verification
1. **Windows quit notice:**
   Run a TeDDy session on Windows and press `q` during an executing action.
   Verify the console prints `Interrupted by user (q). To continue the session, use `teddy resume`.` and the turn report is written.
2. **POSIX quit notice:**
   Run `teddy start` on macOS or Linux and press `q` during an executing action.
   Verify the notice prints and the report is written.
