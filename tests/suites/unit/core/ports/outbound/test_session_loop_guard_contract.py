"""Contract tests: the ISessionLoopGuard outbound port.

The guard's turn and cost baselines are injected at construction. A message
turn must be able to re-anchor them mid-run, so the port exposes an additive
``reset_baseline`` operation. These tests pin that operation's structural
contract (presence and signature) without exercising behavior.

Mirrors the established outbound-port contract convention
(``test_quit_key_listener_contract.py``).
"""

import inspect

from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard


def test_session_loop_guard_exposes_reset_baseline():
    """The port exposes the additive reset_baseline operation."""
    assert hasattr(ISessionLoopGuard, "reset_baseline")


def test_reset_baseline_re_anchors_both_baselines():
    """reset_baseline(turn_count, cumulative_cost) takes exactly two arguments."""
    signature = inspect.signature(ISessionLoopGuard.reset_baseline)
    assert list(signature.parameters) == ["self", "turn_count", "cumulative_cost"]
