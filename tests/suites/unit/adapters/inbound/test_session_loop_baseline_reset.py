"""Unit tests: the session loop re-anchors the guard baseline on a message turn.

A communication (MESSAGE) turn means the human is present and approves
continuation, so the loop re-anchors the guard's budget BEFORE the limit check.
The message turn therefore never trips the limit, and the next segment starts
fresh. A non-communication turn leaves the baseline untouched.
"""

import time
from unittest.mock import Mock

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _orchestrate_session_loop,
)
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.utils.interrupt_guard import InterruptGuard
from tests.harness.setup.container_stub import ContainerStub
from tests.harness.setup.fake_quit_key_listener import FakeQuitKeyListener


class _ActionLog:
    """Minimal action-log double carrying the fields the loop inspects."""

    def __init__(self, action_type: str, details: str) -> None:
        self.action_type = action_type
        self.details = details


def _report(action_type: str, details: str, cumulative_cost: float):
    """Builds a report double carrying one action log."""
    report = Mock(spec=ExecutionReport)
    report.action_logs = [_ActionLog(action_type, details)]
    report.metadata = {"cumulative_cost": cumulative_cost}
    return report


def _run_loop(monkeypatch, loop_guard, report) -> None:
    """Drives one reporting turn then a terminating None turn."""
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *a, **k: None,
    )

    session_manager = Mock(spec=ISessionManager)
    session_manager.get_latest_turn.return_value = "01"
    session_manager.get_cumulative_cost.return_value = 0.0

    calls = {"n": 0}

    def resume(*args, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] > 1:
            return ("test-session", None)
        return ("test-session", report)

    orchestrator = Mock(spec=IRunPlanUseCase)
    orchestrator.resume.side_effect = resume

    container = ContainerStub(
        {
            IRunPlanUseCase: orchestrator,
            ISessionManager: session_manager,
            ISessionLoopGuard: loop_guard,
            InterruptGuard: InterruptGuard(monotonic=time.monotonic),
            IQuitKeyListener: FakeQuitKeyListener(),
        }
    )

    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )


def test_loop_re_anchors_baseline_after_a_message_turn(monkeypatch):
    """A MESSAGE turn re-anchors the baseline at the current turn and cost."""
    loop_guard = Mock(spec=ISessionLoopGuard)
    loop_guard.should_continue.return_value = (True, None)

    _run_loop(monkeypatch, loop_guard, _report("MESSAGE", "Here is my reply", 0.42))

    loop_guard.reset_baseline.assert_called_once_with(1, 0.42)


def test_loop_re_anchors_baseline_before_the_limit_check(monkeypatch):
    """The reset runs BEFORE the limit check so the message turn never trips it."""
    events = []
    loop_guard = Mock(spec=ISessionLoopGuard)

    def _reset(turn_count, cumulative_cost):  # noqa: ARG001
        events.append("reset")

    def _check(turn_count, cumulative_cost, interactive):  # noqa: ARG001
        events.append("check")
        return (True, None)

    loop_guard.reset_baseline.side_effect = _reset
    loop_guard.should_continue.side_effect = _check

    _run_loop(monkeypatch, loop_guard, _report("MESSAGE", "Here is my reply", 0.42))

    assert events == ["reset", "check"]


def test_loop_leaves_baseline_untouched_without_a_message_turn(monkeypatch):
    """A non-MESSAGE turn never re-anchors the baseline."""
    loop_guard = Mock(spec=ISessionLoopGuard)
    loop_guard.should_continue.return_value = (True, None)

    _run_loop(monkeypatch, loop_guard, _report("EXECUTE", "", 0.42))

    loop_guard.reset_baseline.assert_not_called()
