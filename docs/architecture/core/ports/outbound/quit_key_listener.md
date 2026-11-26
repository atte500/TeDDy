# Component Design: IQuitKeyListener
- **Status:** Implemented
- **Classification:** Core Outbound Port
- **Source:** [`src/teddy_executor/core/ports/outbound/quit_key_listener.py`](/src/teddy_executor/core/ports/outbound/quit_key_listener.py)

## Purpose
Defines the lifecycle and trigger hook of a terminal single-key quit listener, so a quit trigger never depends on a terminal delivering a Ctrl+C byte to the application. The port abstracts start/stop plus the trigger callback, keeping the interrupt brackets free of any concrete TTY reader.

## Consumers
- [`Interrupt Scope`](../../../adapters/inbound/interrupt_scope.md): Starts the listener inside the guard's claim window and stops it before the disposition is restored, so the same bracket serves both interruptible boundaries.
- [`CLI Adapter`](../../../adapters/inbound/cli.md): Resolves the listener at the composition root and hands it to the shared seam, so the session loop and the stateless `execute` run bracket identically.

## Dependencies
None — a behavior-free `typing.Protocol` with a Constructor-Injected callback type.

## Class Invariants
- `lifecycle_is_idempotent_and_tty_gated`: `start()` and `stop()` are safe to call more than once and are no-ops when stdin is not a TTY, so a pipeline run never blocks on input and a spurious `stop()` is the cheap failure against a latched install claim.
- `trigger_is_injected`: The quit hook arrives as a Constructor-Injected callback, so the port carries no behavior and an implementation never decides what a press means.

## Inbound Ports
None — this is an outbound port.

## Outbound Ports
- **`IQuitKeyListener`**: `start()`, `stop()`, plus the injected `QuitCallback` a concrete implementation invokes on a press.

## Data Contracts
- **`QuitCallback`** (`Callable[[], None]`): The trigger hook a concrete reader invokes when the quit key is pressed. Constructor-Injected into the implementation so the port itself stays behavior-free.

## Operations

### `start() -> None`
- **Postconditions:** The implementation observes the quit key on the controlling terminal and invokes the injected callback on a press. A no-op when stdin is not a TTY, and safe to call again while already listening.

### `stop() -> None`
- **Postconditions:** Listening stops and any acquired terminal state is released. Idempotent, and a no-op when listening was never started.
