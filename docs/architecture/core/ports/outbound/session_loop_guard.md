- **Status:** Planned

## Purpose / Responsibility
Defines the outbound port for controlling the execution loop of a session. It acts as a safety gate to prevent runaway processes in non-interactive environments.

## Failure Modes
- Ports MUST propagate exceptions if configuration retrieval fails, allowing the Orchestrator to halt the session safely.

## Logic
None (Interface definition).

## Data Contracts / Methods

### `should_continue(current_turn: int, cumulative_cost: float, interactive: bool) -> bool`
Returns `True` if the loop should continue to the next turn. Enforces safety limits strictly when `interactive` is `False` (--yolo).
