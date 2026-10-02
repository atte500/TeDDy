"""Unit tests: session-loop quit-key listener wiring (Bug 56 bare-`q` tracer bullet).

Drives ``_orchestrate_session_loop`` directly -- the session-loop boundary is
the outermost boundary of the quit-key wiring (real TTY key delivery is
impractical in-process). The tracer-bullet contract: the container-composed
quit-key listener is resolved and its ``start()``/``stop()`` lifecycle is paired
with the InterruptGuard handler install/restore around the turn loop, so a
single bare ``q`` (no Enter) exits during the WAITING and EXECUTING windows.

The real reader drives a TTY and is an explicit no-op off-TTY (Contract), so
the lifecycle is observed via the committed ``FakeQuitKeyListener`` conformance
double.
"""

import time
from unittest.mock import Mock

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _orchestrate_session_loop,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.utils.interrupt_guard import InterruptGuard
from tests.harness.setup.container_stub import ContainerStub
from tests.harness.setup.fake_quit_key_listener import FakeQuitKeyListener


def _build_quit_listener_harness(
    listener: FakeQuitKeyListener,
    resume_side_effect: object,
) -> ContainerStub:
    """Container stub wiring the boundary's dependencies behind a fake listener.

    The InterruptGuard is a REAL guard over a spec-bound config double (the
    guard is core logic) so the boundary exercises the real install/restore
    path; the quit-key listener is the shared ``FakeQuitKeyListener``
    conformance double, whose ``lifecycle`` records the start()/stop() pairing
    around the turn loop.
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

    return ContainerStub(
        {
            IRunPlanUseCase: orchestrator,
            ISessionManager: session_manager,
            ISessionLoopGuard: loop_guard,
            IConfigService: config_service,
            InterruptGuard: guard,
            IQuitKeyListener: listener,
        }
    )


def test_quit_listener_lifecycle_wraps_the_turn_loop():
    """The listener must start() before the turn loop and stop() after it."""
    # Arrange
    listener = FakeQuitKeyListener()
    container = _build_quit_listener_harness(
        listener, resume_side_effect=lambda *a, **k: ("test-session", None)
    )

    # Act
    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )

    # Assert: the listener lifecycle brackets the turn loop.
    assert listener.lifecycle == ["start", "stop"]


def test_quit_listener_is_started_before_the_turn_loop_runs():
    """Wiring pin: the listener is STARTED (and not yet stopped) when the turn
    loop executes, so a bare `q` is honoured during the wait windows."""
    # Arrange
    listener = FakeQuitKeyListener()
    observed: list[list[str]] = []

    def capture_lifecycle_and_terminate(*args: object, **kwargs: object):
        observed.append(list(listener.lifecycle))
        return ("test-session", None)

    container = _build_quit_listener_harness(
        listener, resume_side_effect=capture_lifecycle_and_terminate
    )

    # Act
    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )

    # Assert: the listener was running while the turn loop executed.
    assert observed == [["start"]], (
        "the listener must be running while the turn loop executes"
    )


def test_quit_listener_is_stopped_when_the_turn_loop_is_interrupted():
    """Wiring pin: the listener is stopped on the interrupt path too -- its
    stop() must live in the same finally that restores the SIGINT disposition."""
    # Arrange
    listener = FakeQuitKeyListener()
    container = _build_quit_listener_harness(
        listener, resume_side_effect=KeyboardInterrupt
    )

    # Act
    _orchestrate_session_loop(
        container=container,
        session_name="test-session",
        interactive=False,
        no_copy=True,
    )

    # Assert: the listener lifecycle is closed even when the loop is interrupted.
    assert listener.lifecycle == ["start", "stop"]
