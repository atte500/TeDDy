# Component Design: ProductionSessionLoopGuard
- **Status:** Implemented
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
- **Constructor baselines** (`initial_turn`, `initial_cost`): Injected as plain values by the composition root. The two seeds measure the same run from different origins, because their raw inputs do: the turn baseline is `0` and the session loop restarts its counter at `1` on every run, so a resumed session gets this run's full budget rather than one inflated by the turns already spent; the cost baseline is `get_cumulative_cost`, because the report's `cumulative_cost` is session-cumulative, so that delta already starts at zero.
- [`Money`](../utils/money.md): Supplies `format_cost_usd`, which renders both amounts in the cost-limit notice at the one four-decimal standard every surface shares.

## Class Invariants
- `injected_baseline`: The turn-count and cost baselines are injected at construction; every later call is measured as a delta from them. The turn baseline is `0` on every run while the cost baseline is the session's cumulative cost at the start of the run, so a resumed run's budget counts this run in both units despite their different origins.
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
- **Configuration keys:** `guardrails.enabled` (bool, default `True`), `guardrails.max_turns` (int, default `150`), `guardrails.max_session_cost` (float, default `5.0`), `guardrails.message_reset` (bool, default `True`). The `max_turns` default appears in four places that must agree — this page, the config-schema default, the bundled `config.yaml`, and the resolution fallback — because a divergent copy silently restores an undocumented budget. The bundled file and the resolution fallback are pinned against the `GuardrailsConfig` default by `test_bundled_guardrails_agree_with_the_schema_defaults` and `test_default_limits_are_the_pinned_budget`, so a divergence fails by name instead of shipping quietly.
- **Halt reason, turn limit:** the run's turn delta against the limit, followed by the `guardrails.max_turns` key and the config path to edit.
- **Halt reason, cost limit:** the run's cost delta against the configured limit, both rendered by `format_cost_usd` at exactly four decimal places, followed by `guardrails.max_session_cost` and the config path to edit. Both amounts route through the formatter because the notice reports this run's delta rather than the session total, so the `delta/limit` ratio shape survives and four decimals keep it greppable with no thousands separator. One renderer is what stops this notice, the terminal telemetry line, and the reviewer's Context row from stating three different figures for the same session.
- **Path rendering:** the config path is rendered relative to the working directory, so the message stays short and copy-pasteable.

## Operations

### `should_continue(turn_count, cumulative_cost, require_approval) -> tuple[bool, Optional[str]]`
- **Preconditions:** `turn_count` is the caller's own per-run counter, which the session loop restarts at `1` on every run, and `cumulative_cost` is the report's session-cumulative cost; both are measured as deltas from the injected baselines.
- **Postconditions:** Returns `(True, None)` when approval is required, when the guardrail is disabled, or when both deltas are under their limits. Returns `(False, reason)` naming the exceeded limit and the config file to edit.

### `reset_baseline(turn_count, cumulative_cost) -> None`
- **Preconditions:** The caller has just completed a human-approved message turn.
- **Postconditions:** Re-anchors `_initial_turn` and `_initial_cost` when `guardrails.message_reset` is enabled (default `True`); a disabled setting leaves both baselines fixed for the whole run.
