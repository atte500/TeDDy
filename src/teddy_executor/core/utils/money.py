"""The single money presentation standard shared by every surface.

The terminal telemetry line, the guardrail limit notice, and the reviewer's
Context row all answer "what has this session cost?" and must never disagree
about the same figure.
"""

from typing import Any, Mapping, Optional


UNRECORDED_COST_PLACEHOLDER = "$???"


def format_cost_usd(cost: Optional[float]) -> str:
    """Render a monetary amount at exactly four decimal places.

    ``None`` means no figure was recorded and renders as ``$???``; ``0.0`` is a
    recorded free-provider zero and renders as ``$0.0000``. Four decimals is the
    one standard on every surface: it keeps the digits that distinguish two
    runs and absorbs float-accumulation noise below display precision.
    """
    if cost is None:
        return UNRECORDED_COST_PLACEHOLDER
    return f"${cost:.4f}"


def resolve_session_cost(
    meta: Mapping[str, Any], pricing_supported: bool
) -> Optional[float]:
    """Decide whether a turn's accumulated cost is a recorded figure.

    A figure is recorded when the turn carried the explicit recorded-cost signal
    or the provider prices the model. Anything else returns ``None``, which the
    panel and the terminal both render as ``$???``.

    The signal is never inferred from ``cumulative_cost > 0`` because a free
    model legitimately records ``0.0`` and would be indistinguishable from an
    unmeasured turn.
    """
    cost_recorded = meta.get("cost_recorded") is True
    if not pricing_supported and not cost_recorded:
        return None

    return _recorded_amount(meta.get("cumulative_cost"))


def _recorded_amount(value: Any) -> float:
    """Coerce a persisted amount, defaulting an unusable one to a real zero.

    Turn metadata is read straight from YAML, where an absent or malformed
    figure is possible. A recorded turn whose figure cannot be parsed is worth
    ``0.0``, matching the telemetry line's own tolerant parse, so a bad value
    never surfaces as an exception mid-render.
    """
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
