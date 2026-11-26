# Component Design: ISessionLoopGuard
- **Status:** Implemented
- **Classification:** Core Outbound Port
- **Source:** [`src/teddy_executor/core/ports/outbound/session_loop_guard.py`](/src/teddy_executor/core/ports/outbound/session_loop_guard.py)

## Purpose
Defines the outbound port that gates the session execution loop. It stops runaway sessions by enforcing turn-count and cost limits in yolo and pipeline runs.

## Consumers
- [CLI Adapter](../../../adapters/inbound/cli.md): Calls `should_continue` in the session loop to decide whether to advance to the next turn.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `protocol_contract`: The port is a `Protocol`; implementing adapters satisfy the structural contract.
- `failure_propagation`: Implementations must propagate configuration errors, never swallow them.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`ISessionLoopGuard`**: The driven contract consumed by the session loop in the CLI adapter and implemented by the `ProductionSessionLoopGuard` service.

## Data Contracts
- **`should_continue` return:** `(True, None)` to continue, or `(False, reason)` to halt with a human-readable limit message.

## Operations

### `should_continue(turn_count, cumulative_cost, require_approval) -> tuple[bool, Optional[str]]`
- **Preconditions:** `turn_count` is the caller's own per-run counter and `cumulative_cost` is the session-cumulative cost; both are measured as deltas from the baselines the implementation received at construction, so a resumed run's budget counts this run.
- **Postconditions:** Returns `(True, None)` when the loop may continue, or `(False, reason)` when a guardrail limit is hit.

### `reset_baseline(turn_count, cumulative_cost) -> None`
- **Preconditions:** The caller has just completed a human-approved message turn.
- **Postconditions:** Re-anchors the turn-count and cost baselines to the given values, so every later `should_continue` call is measured as a delta from the new baselines.
