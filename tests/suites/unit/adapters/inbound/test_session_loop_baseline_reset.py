"""Unit tests: the session loop seeds and re-anchors the guard baseline.

A communication (MESSAGE) turn means the human is present and approves
continuation, so the loop re-anchors the guard's budget BEFORE the limit check.
The message turn therefore never trips the limit, and the next segment starts
fresh. A non-communication turn leaves the baseline untouched.

A resumed run also gets a fresh per-run budget: the turn baseline is seeded at
zero because the loop's own counter restarts at one, so a session that already
spent forty turns still halts after the configured limit of this run instead of
at a history-inflated count.
"""

import time
from typing import Any
from unittest.mock import Mock, create_autospec

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _orchestrate_session_loop,
)
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.session_loop_guard import ProductionSessionLoopGuard
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


_TURNS_IN_THIS_RUN = 5
_PRIOR_TURNS = 40
_PRIOR_SPEND_USD = 2.0
_RESUMED_TURN_PATH = f".teddy/sessions/test-session/{_PRIOR_TURNS:02d}"


def _environment():
    """System-environment double that reports no process environment overrides."""
    environment = create_autospec(ISystemEnvironment)
    environment.get_env.return_value = None
    return environment


class _GuardConstructingContainer(ContainerStub):
    """Container stub that builds the real guard from the injected baselines.

    The plain stub returns a fixed instance, so the baselines the boundary
    seeds are only observable as recorded arguments. Constructing the real
    guard from those kwargs makes the seeded budget drive the loop's halt
    count, which is what a per-run budget actually guarantees.
    """

    def __init__(self, mapping: dict[type, object], config_service: Any) -> None:
        super().__init__(mapping)
        self._config_service = config_service

    def resolve(self, service_type: type, **kwargs: Any) -> object:
        if service_type is ISessionLoopGuard:
            return ProductionSessionLoopGuard(
                config_service=self._config_service,
                system_environment=_environment(),
                **kwargs,
            )
        return super().resolve(service_type, **kwargs)


def _loop_container(
    mapping: dict[type, object], config_service: Any = None
) -> ContainerStub:
    """Builds the loop's container, carrying the process-global doubles.

    Supplying ``config_service`` builds the real guard from the constructor
    kwargs the boundary injects; omitting it returns the plain stub.
    """
    complete = {
        InterruptGuard: InterruptGuard(monotonic=time.monotonic),
        IQuitKeyListener: FakeQuitKeyListener(),
        **mapping,
    }
    if config_service is None:
        return ContainerStub(complete)
    return _GuardConstructingContainer(complete, config_service)


def _drive_loop(monkeypatch, container) -> None:
    """Runs the session loop against ``container`` until it terminates."""
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *a, **k: None,
    )

    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        require_approval=False,
        no_copy=True,
    )


def _run_loop(monkeypatch, loop_guard, report) -> None:
    """Drives one reporting turn then a terminating None turn."""
    session_manager = Mock(spec=ISessionManager)
    session_manager.get_cumulative_cost.return_value = 0.0

    calls = {"n": 0}

    def resume(*args, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] > 1:
            return ("test-session", None)
        return ("test-session", report)

    orchestrator = Mock(spec=IRunPlanUseCase)
    orchestrator.resume.side_effect = resume

    _drive_loop(
        monkeypatch,
        _loop_container(
            {
                IRunPlanUseCase: orchestrator,
                ISessionManager: session_manager,
                ISessionLoopGuard: loop_guard,
            }
        ),
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

    def _check(turn_count, cumulative_cost, require_approval):  # noqa: ARG001
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


def test_resumed_run_halts_at_the_turn_limit_of_this_run(monkeypatch):
    """A resumed session's turn budget counts this run, not the session's history.

    The session already spent forty turns and 2.00 USD, yet this run must stop
    after ``guardrails.max_turns`` turns. Seeding the baseline with the
    session's history would grow the budget by every turn already spent, so the
    run would only stop at turn 44.
    """
    config_service = create_autospec(IConfigService)
    config_service.get_setting.side_effect = lambda key, default=None: (
        _TURNS_IN_THIS_RUN if key == "guardrails.max_turns" else default
    )
    config_service.get_config_path.return_value = ".teddy/config.yaml"

    session_manager = Mock(spec=ISessionManager)
    session_manager.get_latest_turn.return_value = _RESUMED_TURN_PATH
    session_manager.get_cumulative_cost.return_value = _PRIOR_SPEND_USD

    orchestrator = Mock(spec=IRunPlanUseCase)
    orchestrator.resume.return_value = (
        "test-session",
        _report("EXECUTE", "", _PRIOR_SPEND_USD),
    )

    container = _loop_container(
        {
            IRunPlanUseCase: orchestrator,
            ISessionManager: session_manager,
        },
        config_service,
    )

    _drive_loop(monkeypatch, container)

    assert orchestrator.resume.call_count == _TURNS_IN_THIS_RUN, (
        "A resumed run must get a fresh per-run budget: with "
        f"guardrails.max_turns={_TURNS_IN_THIS_RUN} on a session already at "
        f"turn {_PRIOR_TURNS}, the loop must halt after "
        f"{_TURNS_IN_THIS_RUN} turns, but it resumed "
        f"{orchestrator.resume.call_count} times."
    )
