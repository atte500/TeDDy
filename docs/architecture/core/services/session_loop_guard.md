# Component Design: ProductionSessionLoopGuard
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/session_loop_guard.py`](/src/teddy_executor/core/services/session_loop_guard.py)

## Purpose
Implements the `ISessionLoopGuard` outbound port. It stops runaway non-interactive sessions by enforcing turn-count and cost limits relative to a baseline injected at construction.

## Consumers
- [CLI Adapter](../../adapters/inbound/cli.md): Calls `should_continue` in the session loop to decide whether to advance to the next turn.
- [Composition Root](/src/teddy_executor/container.py): Registers `ProductionSessionLoopGuard` against `ISessionLoopGuard`.

## Dependencies
- [`IConfigService`](../ports/outbound/config_service.md): Reads the `yolo_guardrails.*` limits and the config path.

## Class Invariants
- `injected_baseline`: The turn-count and cost baselines are injected at construction; every later call is measured as a delta from them.
- `interactive_always_continues`: An interactive session always returns `(True, None)`.
- `failure_propagation`: Configuration errors propagate and are never swallowed.

## Inbound Ports
None — this is a concrete implementation of an outbound port.

## Outbound Ports
- **`ISessionLoopGuard`**: The driven contract implemented by this service. See the [ISessionLoopGuard design](../ports/outbound/session_loop_guard.md).

## Data Contracts
- **`should_continue` return:** `(True, None)` to continue, or `(False, reason)` to halt with a human-readable limit message.
- **Configuration keys:** `yolo_guardrails.enabled` (bool, default `True`), `yolo_guardrails.max_turns` (int, default `99`), `yolo_guardrails.max_session_cost` (float, default `5.0`).

## Operations

### `should_continue(turn_count, cumulative_cost, interactive) -> tuple[bool, Optional[str]]`
- **Preconditions:** `turn_count` and `cumulative_cost` are measured as deltas from the process-start baseline.
- **Postconditions:** Returns `(True, None)` when interactive mode is active, when the guardrail is disabled, or when both deltas are under their limits. Returns `(False, reason)` naming the exceeded limit and the config file to edit.
