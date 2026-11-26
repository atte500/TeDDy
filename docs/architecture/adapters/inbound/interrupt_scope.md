# Component Design: Interrupt Scope
- **Status:** Implemented
- **Classification:** Inbound Adapter
- **Source:** [`src/teddy_executor/adapters/inbound/interrupt_scope.py`](/src/teddy_executor/adapters/inbound/interrupt_scope.py)

## Purpose
Owns the process-global interrupt bracket for every boundary that can run an action: it takes the SIGINT disposition, starts the quit-key listener, and releases both in a `finally` on every exit path. It exists so the lifecycle has exactly one owner, because two boundaries taking independent `install()` snapshots would each restore the other's handler.

## Consumers
- **Session loop** (`_orchestrate_session_loop` in `session_cli_handlers.py`): Wraps the turn loop so a `q` or Ctrl+C drains the running plan instead of escaping, and the loop exits the turn after a drain.
- [`CLI Adapter`](./cli.md): Wraps the stateless `execute` command body, covering plan resolution, the use-case invocation, the invalid-plan handler, and the report gate, so a validation `typer.Exit` unwinds through the same release.

## Dependencies
- [`InterruptGuard`](../../core/utils/interrupt_guard.md): The single holder of the SIGINT disposition, injected already resolved. The seam constructs no concrete guard, so it never becomes a second owner by accident.
- [`IQuitKeyListener`](../../core/ports/outbound/quit_key_listener.md): The terminal single-key reader, injected already resolved. Its `stop()` is documented as idempotent and a no-op off-TTY, which is what makes a spurious stop the cheap failure.

## Class Invariants
- `single_owner_of_sigint_disposition`: Every interruptible boundary enters this seam rather than installing a handler, so no two snapshots can interleave and restore each other's disposition.
- `release_on_every_exit_path`: The listener stops and the disposition is restored in `finally`, so a raising action, a `typer.Exit`, and a `KeyboardInterrupt` all unwind through the same release.
- `stop_before_restore`: `listener.stop()` runs before `guard.restore()`, because no keystroke may be read while the previous handler comes back.
- `start_inside_the_claim_window`: `listener.start()` runs after `guard.install()`, so a raising start cannot orphan the install claim and leave the guard unusable for the next boundary.
- `transient_press_state_cleared_on_entry`: Entry clears the guard's recorded press source, because one memoized container keeps a single guard alive across in-process commands and a stale source would name the previous run's key in this run's notice.
- `never_swallows_interrupt_or_exit`: The seam owns only the lifecycle; it re-raises both a `KeyboardInterrupt` and a `typer.Exit`, because the boundary that entered the bracket owns the notice and the exit code.

## Inbound Ports
None — this is a module-level seam composed at the CLI boundary, not a port implementation.

## Outbound Ports
None declared. It receives its two collaborators already resolved: an `InterruptGuard` (core utility) and an `IQuitKeyListener` (outbound port).

## Data Contracts
None — the seam exchanges no DTO and raises no custom exception.

## Operations

### `interrupt_scope(guard, listener) -> Iterator[InterruptGuard]`
- **Preconditions:** `guard` is not currently claiming the process disposition; a nested install violates the guard's own install contract and fails its runtime assertion naming the held disposition. `listener` is either a real reader or a no-op double.
- **Postconditions:** For the duration of the `with` body the guard's handler is the process SIGINT disposition and the listener is started. On exit — normal, raising, `typer.Exit`, or `KeyboardInterrupt` — the listener is stopped and the previously captured disposition is reinstated, releasing the guard's claim so a later in-process bracket installs normally. The body receives the same guard for readability.
- **Exceptions:**
  - `KeyboardInterrupt`: Propagated after release so the boundary can print the interrupt notice instead of a traceback.
  - `typer.Exit`: Propagated after release so an exit code never bypasses restoration.
