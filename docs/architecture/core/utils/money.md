# Component Design: Money
- **Status:** Implemented
- **Classification:** Core Utility
- **Source:** [`src/teddy_executor/core/utils/money.py`](/src/teddy_executor/core/utils/money.py)

## Purpose
A stateless module holding the one money presentation standard every surface shares, together with the recorded-cost decision behind it. The terminal telemetry line, the guardrail limit notice, and the reviewer's Context row all answer "what has this session cost?" through it, so they cannot disagree about the same figure.

## Consumers
- [`PlanningService`](../services/planning_service.md): Renders the terminal Session Cost line and decides whether the turn's accumulated cost is a recorded figure.
- [`ProductionSessionLoopGuard`](../services/session_loop_guard.md): Renders both amounts of the cost-limit notice, which reports this run's delta against the configured limit rather than the session total.
- [TextualPlanReviewer](../../adapters/inbound/textual_plan_reviewer.md): Renders the Context panel's Session Cost row.

## Dependencies
None. The module imports only the standard library (`typing`).

## Class Invariants
- `stateless_pure_functions`: Every helper is a pure function of its arguments; the module holds no state and reads no port.
- `one_precision_everywhere`: A recorded amount renders at exactly four decimal places with no thousands separator, so two figures compare at a glance and the guardrail notice stays greppable.
- `absence_is_not_zero`: `None` means no figure was recorded and renders `$???`; `0.0` is a recorded free-provider zero and renders `$0.0000`. The two facts never render alike.
- `recorded_signal_never_inferred_from_amount`: The decision rests on the turn's explicit recorded-cost signal or on the provider pricing the model, never on `cumulative_cost > 0`, because a free model legitimately records `0.0` and would otherwise be indistinguishable from an unmeasured turn.
- `amount_coercion_only_degrades_the_figure`: A private coercion turns an absent or unparseable persisted amount into `0.0`, matching the telemetry line's own tolerant parse, so a malformed YAML value never raises mid-render; the decision whether a figure was recorded still rests solely on the recorded signal.

## Inbound Ports
None — this module is an internal helper surface.

## Outbound Ports
None — the module declares no injected dependencies.

## Data Contracts
- **Rendered money string**: `"$"` followed by exactly four decimal places for a recorded amount, or the unrecorded placeholder.
- **`UNRECORDED_COST_PLACEHOLDER`**: The `$???` literal, single-sourced so no caller spells its own.
- **Recorded-cost decision**: `Optional[float]` — the accumulated figure when the turn recorded one, otherwise `None`.

## Operations

### `format_cost_usd(cost) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns `$` plus the amount at exactly four decimal places, or `$???` when `cost` is `None`. Float-accumulation noise below display precision (`1.2000000000000002`) renders as `$1.2000`.
- **Exceptions:** None.

### `resolve_session_cost(meta, pricing_supported) -> Optional[float]`
- **Preconditions:** `meta` is a turn metadata mapping; `pricing_supported` reports whether the provider prices the resolved model.
- **Postconditions:** Returns the accumulated cost when the turn carried the recorded-cost signal or the model is priced, and `None` otherwise, which every renderer shows as `$???`. A decided figure whose persisted amount is absent or malformed reads as `0.0`.
- **Exceptions:** None.
