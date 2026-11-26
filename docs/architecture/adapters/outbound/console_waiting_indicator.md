# Component Design: WaitingIndicator
- **Status:** Implemented
- **Classification:** Outbound Adapter
- **Source:** [`src/teddy_executor/adapters/outbound/console_waiting_indicator.py`](/src/teddy_executor/adapters/outbound/console_waiting_indicator.py)

## Purpose
Owns the single transient stderr line drawn while a model generates a plan. It opens a rich live region, renders one spinner frame per refresh, and erases the region on completion, so a slow generation looks alive while the settled output stays byte-identical.

## Consumers
- [`ConsoleInteractorAdapter`](./console_interactor.md): Forwards `begin_waiting` and `end_waiting` to it, so the waiting surface has one implementation.

## Dependencies
- **`rich.console.Console`**: The injected console whose `is_terminal` gates every render.
- **`rich.live.Live`** (bound by `create_indicator`): The transient region hosting the animation.
- **`atexit`** (adapted by `AtexitExitHooks`, bound by `create_indicator`): The exit-hook registry that erases a region abandoned by a killed daemon worker. It is reached through an adapter because `atexit.register` returns the callable it receives and accepts forwarded arguments, so the module is not structurally assignable to `IExitHooks`.

## Class Invariants
- `terminal_gate`: Without an attached terminal no region is ever created, because `Live.stop()` renders and a stray line would corrupt redirected logs and CI transcripts.
- `single_region`: At most one region is open; `begin` while a region is open replaces the label without stacking a second region.
- `never_raise`: Both operations report a rendering failure through `logger.warning` and return, because `begin_waiting` runs outside the planning `try` and `end_waiting` runs inside a `finally`.
- `hook_per_wait`: The exit hook is registered with `begin` and removed before `stop`, so an abandoned region still restores the cursor and a repeated `end` stays silent.
- `own_line_only`: The region redraws nothing but its own transient line, so the waiting banner, the telemetry block, and the plan summary are never rewritten.
- `frame_counter`: Successive refreshes advance an internal frame counter instead of reading a clock, so the animation is deterministic in tests.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IWaitingIndicator`**: The waiting surface implemented by this adapter and consumed by `ConsoleInteractorAdapter`.
- **`ILiveRegion`**: The narrow slice of a rich `Live` region the indicator drives (`start` / `stop`).
- **`IExitHooks`**: The exit-hook registry shape (`register` / `unregister`). `AtexitExitHooks` adapts the `atexit` module to it; the module itself is not structurally assignable, because its `register` returns the callable and accepts forwarded arguments.

## Data Contracts
- **`LiveFactory`**: `Callable[[Console, Callable[[], Text]], ILiveRegion]` — builds the region for one wait.
- **`SPINNER_FRAMES`**: The braille glyphs advanced one per refresh.
- **`SPINNER_REFRESH_PER_SECOND`**: The region's refresh rate.
- **Transient line**: `{glyph} {message}` styled cyan, returned by the callable the region re-invokes.

## Operations

### `begin(message) -> None`
- **Preconditions:** `message` is a short presentation hint; a region may already be open.
- **Postconditions:** On a terminal console, opens a transient region beneath the telemetry or replaces the label of the open one. A rendering failure is logged and leaves neither a region nor an exit hook behind.
- **Exceptions:** None — a display failure never propagates into the turn.

### `end() -> None`
- **Preconditions:** None; calling it with no open region is a silent no-op.
- **Postconditions:** Erases the open region after clearing the region reference and removing the exit hook, so a failing stop strands nothing and a repeated call does nothing.
- **Exceptions:** None — teardown runs inside a `finally` and must not corrupt the error that ended the wait.

### `create_live(console, get_renderable, live_class) -> LiveRegionT`
- **Preconditions:** `live_class` is a region class supplied by the caller — rich's `Live` in production, a recording double in tests.
- **Postconditions:** Returns an instance of exactly the class it was handed, so a caller that passes a concrete class keeps that type and can observe the region's own lifecycle. The region is transient with `redirect_stdout=False` and `redirect_stderr=False`, because rich enables redirection unconditionally in `start()` and a worker thread would otherwise swap the process-global streams.

### `create_indicator(console) -> WaitingIndicator`
- **Preconditions:** `console` is the stderr console the adapter renders through.
- **Postconditions:** Returns the production indicator, binding `_production_live_factory` (rich's `Live`) and `AtexitExitHooks` (`atexit`), so no concrete default enters the indicator's constructor.
