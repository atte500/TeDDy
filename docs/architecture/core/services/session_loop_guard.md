# Component Design: ProductionSessionLoopGuard
- **Status:** Refactoring
- **Classification:** Core Service
- **Source:** [`src/teddy_executor/core/services/session_loop_guard.py`](/src/teddy_executor/core/services/session_loop_guard.py)

## Purpose
Implements the `ISessionLoopGuard` outbound port. It stops runaway yolo and pipeline sessions by enforcing turn-count and cost limits relative to a baseline injected at construction.

## Consumers
- [CLI Adapter](../../adapters/inbound/cli.md): Calls `should_continue` in the session loop to decide whether to advance to the next turn.
- [Composition Root](/src/teddy_executor/container.py): Registers `ProductionSessionLoopGuard` against `ISessionLoopGuard`.

## Dependencies
- [`IConfigService`](../ports/outbound/config_service.md): Reads `guardrails.enabled`, `guardrails.max_turns`, `guardrails.max_session_cost`, and `guardrails.message_reset`, and supplies the config path the halt reason names.
- [`ISystemEnvironment`](../ports/outbound/environment_inspector.md): Reads the `TEDDY_MAX_TURNS` and `TEDDY_MAX_SESSION_COST` overrides.
- **Constructor baselines** (`initial_turn`, `initial_cost`): Injected as plain values by the composition root, which seeds them from the session's persisted totals so a resumed run's delta starts at zero.

## Class Invariants
- `injected_baseline`: The turn-count and cost baselines are injected at construction; every later call is measured as a delta from them.
- `approval_always_continues`: A run that requires approval always returns `(True, None)`, because a human already gates every turn.
- `enabled_gate`: A false `guardrails.enabled` returns `(True, None)`, because the operator opted out of unattended bounds entirely.
- `precedence`: One resolution order serves both limits — explicit constructor override, then environment variable, then `guardrails.<key>`, then the default.
- `override_absent_is_none_only`: A constructor override counts as present whenever it is not `None`, so an explicit `--max-turns 0` halts before the first turn; an environment variable counts as present only when non-empty, so an empty export falls through to config.
- `config_zero_is_absent`: The config read is `value or default`, so a configured `0` restores the default, because an accidental zero would halt every unattended run instantly.
- `failure_propagation`: Configuration errors propagate and are never swallowed.

## Inbound Ports
None — this is a concrete implementation of an outbound port.

## Outbound Ports
- **`ISessionLoopGuard`**: The driven contract implemented by this service. See the [ISessionLoopGuard design](../ports/outbound/session_loop_guard.md).

## Data Contracts
- **`should_continue` return:** `(True, None)` to continue, or `(False, reason)` to halt with a human-readable limit message. A reached limit is never signalled by an exception, because a guardrail that raised would be indistinguishable from a defect.
- **Configuration keys:** `guardrails.enabled` (bool, default `True`), `guardrails.max_turns` (int, default `150`), `guardrails.max_session_cost` (float, default `5.0`), `guardrails.message_reset` (bool, default `True`). The `max_turns` default appears in four places that must agree — this page, the config-schema default, the bundled `config.yaml`, and the resolution fallback — because a divergent copy silently restores an undocumented budget.
- **Halt reason, turn limit:** the run's turn delta against the limit, followed by the `guardrails.max_turns` key and the config path to edit.
- **Halt reason, cost limit:** the run's cost delta and the limit, both rendered by `format_cost_usd` (`core/utils/money.py`, delivered by slice 04-05) at exactly four decimal places instead of a local `:.2f` format string, followed by `guardrails.max_session_cost` and the config path to edit. This notice is one of the two monetary format sites in `src` today — `PlanningService`'s terminal Session Cost line (`planning_service.py:287`) is the other, and it already renders four decimals, so this notice is the single site whose format changes. The shared formatter replaces both rather than joining them: one renderer is what stops this line, the terminal telemetry line, and the reviewer's Context row from stating three different figures for the same session.
- **Path rendering:** the config path is rendered relative to the working directory, so the message stays short and copy-pasteable.

## Operations

### `should_continue(turn_count, cumulative_cost, require_approval) -> tuple[bool, Optional[str]]`
- **Preconditions:** `turn_count` and `cumulative_cost` are measured as deltas from the process-start baseline.
- **Postconditions:** Returns `(True, None)` when approval is required, when the guardrail is disabled, or when both deltas are under their limits. Returns `(False, reason)` naming the exceeded limit and the config file to edit.

### `reset_baseline(turn_count, cumulative_cost) -> None`
- **Preconditions:** The caller has just completed a human-approved message turn.
- **Postconditions:** Re-anchors `_initial_turn` and `_initial_cost` when `guardrails.message_reset` is enabled (default `True`); a disabled setting leaves both baselines fixed for the whole run.
