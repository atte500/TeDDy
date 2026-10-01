"""Unit tests: session-loop interrupt wiring (tracer bullet).

Drives `_orchestrate_session_loop` directly — the session-loop boundary
is the outermost boundary of the interrupt wiring (real SIGINT at the
CliRunner level is impractical in-process). The tracer-bullet contract:
the container-composed InterruptGuard is resolved and installed around
the turn loop, and a KeyboardInterrupt escaping the loop is caught at
the boundary with a termination notice (immediate-exit semantics:
nothing is in flight, no report, the process exits cleanly).
"""

import signal
import time
from unittest.mock import Mock

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _orchestrate_session_loop,
)
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.utils.interrupt_guard import InterruptGuard


class _ContainerStub:
    """Hand-rolled punq-compatible container double (no bare MagicMock)."""

    def __init__(self, mapping: dict[type, object]) -> None:
        self._mapping = mapping

    def resolve(self, service_type: type, **kwargs: object) -> object:
        service = self._mapping.get(service_type)
        if service is None:
            return Mock()
        return service


def _build_interrupt_harness(
    resume_side_effect: object = KeyboardInterrupt,
) -> tuple[_ContainerStub, Mock]:
    """Container stub + orchestrator double for the interrupt wiring.

    The InterruptGuard is a REAL guard over a spec-bound config double
    (the guard is core logic — real domain objects, not mock stand-ins);
    by default the orchestrator double raises KeyboardInterrupt from
    resume() to simulate a Ctrl+C escaping the turn loop; tests pinning
    the handler lifecycle inject a capturing side_effect instead.
    """
    config_service = Mock(spec=IConfigService)
    config_service.get_setting.side_effect = lambda key, default=None: default

    session_manager = Mock(spec=ISessionManager)
    session_manager.get_latest_turn.return_value = "01"
    session_manager.get_cumulative_cost.return_value = 0.0

    loop_guard = Mock(spec=ISessionLoopGuard)
    loop_guard.should_continue.return_value = (True, None)

    orchestrator = Mock(spec=IRunPlanUseCase)
    orchestrator.resume.side_effect = resume_side_effect

    guard = InterruptGuard(config_service=config_service, monotonic=time.monotonic)

    container = _ContainerStub(
        {
            IRunPlanUseCase: orchestrator,
            ISessionManager: session_manager,
            ISessionLoopGuard: loop_guard,
            IConfigService: config_service,
            InterruptGuard: guard,
        }
    )
    return container, orchestrator


def test_session_loop_catches_keyboard_interrupt_with_termination_notice(capsys):
    """A KeyboardInterrupt escaping the turn loop must be caught at the
    session-loop boundary and surfaced as a termination notice — not
    propagate as a raw traceback."""
    # Arrange
    container, _ = _build_interrupt_harness()

    # Act
    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )

    # Assert: the boundary converts the signal into the termination notice.
    captured = capsys.readouterr()
    assert "Interrupted by user (Ctrl+C)" in captured.out


def test_handler_installed_during_the_turn_loop(monkeypatch):
    """Wiring pin: the guard's SIGINT handler is installed while the turn
    loop runs — the orchestrator's resume() executes under the
    container-composed guard's handler, not the default disposition."""
    # Arrange
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *args, **kwargs: None,
    )
    observed_handlers: list[object] = []

    def capture_handler_and_terminate(
        *args: object, **kwargs: object
    ) -> tuple[str, None]:
        observed_handlers.append(signal.getsignal(signal.SIGINT))
        return ("test-session", None)

    container, _ = _build_interrupt_harness(
        resume_side_effect=capture_handler_and_terminate
    )
    guard = container.resolve(InterruptGuard)

    # Act
    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )

    # Assert: resume() ran inside the guard's handler window.
    assert observed_handlers, "resume() must observe the installed SIGINT handler"
    assert observed_handlers[0] == guard._handle_signal


def test_previous_sigint_disposition_restored_after_the_loop(monkeypatch):
    """Wiring pin: the session-loop boundary owns the handler lifecycle —
    the pre-loop SIGINT disposition is restored once the loop exits."""
    # Arrange
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *args, **kwargs: None,
    )
    previous = signal.getsignal(signal.SIGINT)
    assert previous is not None
    container, _ = _build_interrupt_harness(
        resume_side_effect=lambda *args, **kwargs: ("test-session", None)
    )

    try:
        # Act
        _orchestrate_session_loop(
            container=container,
            session_name="test-session",
            interactive=False,
            no_copy=True,
        )

        # Assert: the boundary restored the caller's disposition.
        assert signal.getsignal(signal.SIGINT) is previous
    finally:
        signal.signal(signal.SIGINT, previous)


def test_container_guard_identity_across_boundary_and_ports_factory(container):
    """Wiring pin: the boundary's guard and the ports-factory guard are the
    SAME instance — the singleton scope shares the WAITING/EXECUTING phase
    state and the interrupted drain flag across the composition root."""
    # Arrange / Act
    guard = container.resolve(InterruptGuard)
    ports = container.resolve(OrchestratorPorts)

    # Assert: one process-global guard instance serves both consumers.
    assert ports.interrupt_guard is guard
