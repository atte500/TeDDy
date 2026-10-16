# Component Design: ISessionLoopGuard
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/session_loop_guard.py`](/src/teddy_executor/core/ports/outbound/session_loop_guard.py)

## Purpose
Defines the outbound port that gates the session execution loop. It stops runaway sessions by enforcing turn-count and cost limits in non-interactive runs.

## Consumers
- [`SessionOrchestrator`](../../services/session_orchestrator.md): Decides whether the session advances to the next turn.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `protocol_contract`: The port is a `Protocol`; implementing adapters satisfy the structural contract.
- `failure_propagation`: Implementations must propagate configuration errors, never swallow them.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`ISessionLoopGuard`**: The driven contract consumed by `SessionOrchestrator` and implemented by the `SessionLoopGuard` service.

## Data Contracts
- **`should_continue` return:** `(True, None)` to continue, or `(False, reason)` to halt with a human-readable limit message.

## Operations

### `should_continue(turn_count, cumulative_cost, interactive) -> tuple[bool, Optional[str]]`
- **Preconditions:** `turn_count` and `cumulative_cost` are measured as deltas from the process-start baseline.
- **Postconditions:** Returns `(True, None)` when the loop may continue, or `(False, reason)` when a guardrail limit is hit.
