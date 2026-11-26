import pytest

from teddy_executor.core.utils.money import format_cost_usd, resolve_session_cost


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        (0.42, "$0.4200"),
        (1.234567, "$1.2346"),
        (0.1, "$0.1000"),
        (0.0, "$0.0000"),
        (0.00004, "$0.0000"),
        (1234.5, "$1234.5000"),
        (1.2000000000000002, "$1.2000"),
    ],
)
def test_a_recorded_cost_renders_at_exactly_four_decimals(cost: float, expected: str):
    """Four decimals is the one standard every surface renders, so two figures compare."""
    assert format_cost_usd(cost) == expected


def test_an_unrecorded_cost_renders_as_an_honest_placeholder():
    """None means no figure was recorded, never a fabricated zero."""
    assert format_cost_usd(None) == "$???"


def test_a_turn_that_recorded_its_cost_reports_the_cumulative_total():
    """A recorded signal makes the ledger figure meaningful even on an unpriced model."""
    meta = {"cumulative_cost": 0.42, "cost_recorded": True}

    assert resolve_session_cost(meta, pricing_supported=False) == 0.42


def test_a_priced_model_reports_the_cumulative_total_without_a_recorded_signal():
    """A priced model already implies the provider accounted for the turn."""
    meta = {"cumulative_cost": 0.42}

    assert resolve_session_cost(meta, pricing_supported=True) == 0.42


def test_an_unrecorded_cost_returns_none_when_neither_signal_is_present():
    """No recorded signal and no pricing means nothing was measured."""
    meta = {"cumulative_cost": 0.42, "cost_recorded": False}

    assert resolve_session_cost(meta, pricing_supported=False) is None


def test_a_priced_model_without_an_accumulated_total_reports_a_recorded_zero():
    """An empty ledger for a priced model is a real zero, not a missing figure."""
    assert resolve_session_cost({}, pricing_supported=True) == 0.0


def test_a_malformed_accumulated_total_reads_as_a_recorded_zero():
    """A recorded turn whose figure cannot be parsed must not break the render."""
    meta = {"cumulative_cost": "unavailable", "cost_recorded": True}

    assert resolve_session_cost(meta, pricing_supported=False) == 0.0
