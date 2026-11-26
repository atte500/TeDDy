# Component Design: Interrupt Guard
- **Status:** Implemented
- **Classification:** Core Utility
- **Source:** [`src/teddy_executor/core/utils/interrupt_guard.py`](/src/teddy_executor/core/utils/interrupt_guard.py)

## Purpose
Owns the process SIGINT disposition and the two-phase interrupt policy: in the WAITING phase a signal raises `KeyboardInterrupt` immediately because nothing is in flight, and in the EXECUTING phase a first signal sets a drain flag so in-flight work can stop gracefully while a second signal inside the grace window escalates to immediate termination. It also records which key caused the interrupt, so a boundary notice can name the key the user actually pressed.

## Consumers
- [`Interrupt Scope`](../../adapters/inbound/interrupt_scope.md): The single bracket that calls `install()` and `restore()`, so exactly one instance owns the disposition for the whole run.
- [`CLI Adapter`](../../adapters/inbound/cli.md): Resolves the guard at both interruptible boundaries — the session loop and the stateless `execute` run — and reads `interrupted` to decide the drain notice and the exit path.
- **Quit-key listener callback**: Records the pressed key through `record_source` before self-delivering SIGINT, so a drained run reports `q` rather than the `Ctrl+C` default.

## Dependencies
- **Constructor-injected monotonic clock** (`Callable[[], float]`): The only dependency. Production passes `time.monotonic`; tests pass a controllable fake so the grace window is exercised without sleeping.
- **`signal` (standard library)**: Owns the disposition through `signal.signal` and delivers in-process presses through `raise_interrupt`.

## Class Invariants
- `single_claim_per_instance`: One guard holds at most one SIGINT claim. `install()` asserts the claim sentinel is free before taking a snapshot, and `restore()` asserts a claim is held before releasing it. A dedicated sentinel — not `None` — marks "unclaimed", because `signal.getsignal()` may legitimately return `None` for a handler not set from Python.
- `claim_released_not_latched`: `restore()` reinstates the captured disposition and clears the claim, so one memoized-container guard can bracket a later in-process command while a genuine nested install still fails its contract.
- `phase_decides_the_signal_response`: `_executing` alone selects between an immediate raise in WAITING and the drain-then-escalate policy in EXECUTING, so no mid-logic environment check or configuration read participates.
- `grace_window_is_a_code_constant`: `GRACE_WINDOW_SECONDS` is a module constant per an explicit product decision, documented as a deliberate exception to the centralized-configuration law rather than an overlooked magic number.
- `drain_flag_cleared_at_executing_entry`: `enter_executing()` clears `interrupted` on entry, so a flag left by a previous action cannot skip the next one.

## Inbound Ports
None — a core utility consumed directly by the interrupt seam, not a port implementation.

## Outbound Ports
None declared. Its time source is a Constructor-Injected callable and its process interaction is the standard library `signal` module.

## Data Contracts
- **`GRACE_WINDOW_SECONDS`** (`float`, module constant): How long after a first EXECUTING signal a second one escalates to immediate termination. A later second signal is treated as a new first signal and restarts the window.
- **`INTERRUPT_REASON`** (`str`, module constant): The single user-visible drain reason (`Interrupted by user.`), shared by the boundary notice and the audit-trail drain reason so the two cannot drift.
- No custom exception type: contract failures are runtime assertions (strippable under `python -O`), and a WAITING press raises the built-in `KeyboardInterrupt`.

## Operations

### `install() -> object`
- **Preconditions:** The instance holds no claim; a second install without an intervening `restore()` is a programming defect.
- **Postconditions:** `_handle_signal` becomes the process SIGINT disposition, the previous disposition is stored for restoration, and it is returned for callers that only inspect it.
- **Exceptions:** `AssertionError` naming the disposition the guard already holds.

### `restore() -> None`
- **Preconditions:** The instance holds a claim from a matching `install()`.
- **Postconditions:** The captured disposition is reinstated and the claim returns to the sentinel, so a later bracket installs normally.
- **Exceptions:** `AssertionError` when no claim is held, instead of silently installing a foreign handler.

### `clear_source() -> None`
- **Postconditions:** `source` is `None`, so the next run's notice cannot name the previous run's key. Called at bracket entry, because one memoized container keeps a single guard alive across in-process commands.

### `record_source(source: str) -> None`
- **Postconditions:** `source` names the key that triggered the interrupt, recorded before the listener self-delivers SIGINT.

### `enter_waiting() -> Iterator[InterruptGuard]`
- **Postconditions:** For the duration of the block a SIGINT raises `KeyboardInterrupt` immediately, because nothing is in flight. Exiting resets the first-signal timestamp.

### `enter_executing() -> Iterator[InterruptGuard]`
- **Postconditions:** For the duration of the block the first SIGINT sets `interrupted` and returns; a second within the grace window raises `KeyboardInterrupt`; a later second signal restarts the window. Entry clears `interrupted` and exit returns to the raising phase.

### `raise_interrupt() -> None` (module function)
- **Postconditions:** SIGINT is delivered in-process so the installed handler runs on every platform: `signal.pthread_kill` targets the main thread on POSIX, and Windows or a platform without `pthread_kill` falls back to `signal.raise_signal`.
