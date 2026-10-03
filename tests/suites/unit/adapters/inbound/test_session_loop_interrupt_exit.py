"""Unit tests: the session loop EXITS after an interrupt drain (Bug 58 Option B).

Once a bare `q`/Ctrl+C has drained a plan (in-flight action terminated,
remaining actions skipped, report.md finalized), the turn loop must stop
instead of auto-advancing to the next turn, so the user regains control.
"""

import time
from unittest.mock import Mock

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _orchestrate_session_loop,
)
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.utils.interrupt_guard import InterruptGuard
from tests.harness.setup.container_stub import ContainerStub
from tests.harness.setup.fake_quit_key_listener import FakeQuitKeyListener


def test_session_loop_exits_after_an_interrupt_drain(monkeypatch):
    # Arrange: suppress report printing (a Mock report would otherwise crash).
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *a, **k: None,
    )

    config_service = Mock(spec=IConfigService)
    config_service.get_setting.side_effect = lambda key, default=None: default

    session_manager = Mock(spec=ISessionManager)
    session_manager.get_latest_turn.return_value = "01"
    session_manager.get_cumulative_cost.return_value = 0.0

    loop_guard = Mock(spec=ISessionLoopGuard)
    loop_guard.should_continue.return_value = (True, None)

    guard = InterruptGuard(monotonic=time.monotonic)

    report = Mock(spec=ExecutionReport)
    report.action_logs = []
    report.metadata = {}

    calls = {"n": 0}

    def resume(*args, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        # Simulate a bare `q` having drained the plan during execution.
        guard.interrupted.set()
        return ("test-session", report)

    orchestrator = Mock(spec=IRunPlanUseCase)
    orchestrator.resume.side_effect = resume

    container = ContainerStub(
        {
            IRunPlanUseCase: orchestrator,
            ISessionManager: session_manager,
            ISessionLoopGuard: loop_guard,
            IConfigService: config_service,
            InterruptGuard: guard,
            IQuitKeyListener: FakeQuitKeyListener(),
        }
    )

    # Act
    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )

    # Assert: the loop stopped after the interrupt drain (did NOT auto-advance).
    assert calls["n"] == 1
