- **Status:** Planned

## Purpose / Responsibility
Defines the outbound port for controlling the execution loop of a session. It acts as a safety gate to prevent runaway processes in non-interactive environments.

## Failure Modes
- Ports MUST propagate exceptions if configuration retrieval fails, allowing the Orchestrator to halt the session safely.

## Logic
None (Interface definition).

## Data Contracts / Methods

### `should_continue(turn_count: int, cumulative_cost: float, interactive: bool) -> tuple[bool, str | None]`
Returns `(True, None)` if the loop should continue to the next turn. Returns `(False, reason)` when a guardrail limit is hit, where `reason` is a human-readable message explaining which limit was exceeded and how to adjust the configuration. Limits are calculated as deltas from the process-start baseline.
