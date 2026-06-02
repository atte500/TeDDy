- **Status:** Planned

## Purpose / Responsibility
The `SessionLoopGuard` acts as a safety "Stop the Line" mechanism for automated execution. It prevents infinite loops and runaway costs by enforcing limits configured under `yolo_guardrails`.

## Failure Modes
- **Config Missing**: If `yolo_guardrails` is absent, the guard defaults to conservative limits (10 turns, $1.00) rather than failing open.

## Ports
- **Inbound**: `ISessionLoopGuard`
- **Outbound**: `IConfigService`

## Implementation Details / Logic
### Process-Relative Tracking
To support resuming sessions without immediate limit hits, the guard captures the **Session Baseline** upon the first call in a process:
1. `initial_turn`: The turn count of the first call.
2. `initial_cost`: The cumulative cost of the first call.

### Enforcement Logic (`should_continue`)
1. **Interactive Check**: If `interactive=True`, always return `True`.
2. **Relative Delta Check**:
   - `delta_turns = current_turn - initial_turn`
   - `delta_cost = current_cost - initial_cost`
   - Return `False` if either `delta_turns >= max_turns` or `delta_cost >= max_cost`.

## Data Contracts / Methods
### `should_continue(current_turn: int, current_cost: float, interactive: bool) -> bool`
Checks process-relative deltas against configured `yolo_guardrails`.
