"""Unit tests: InterruptGuard seam into ExecutionOrchestrator.

Drives the non-breaking seam expansion injecting the two-phase Ctrl+C
guard (deliverable-7 contract) into the execution orchestrator chain:
an optional `interrupt_guard` field on the frozen `OrchestratorPorts`
DTO (mirroring the optional `plan_reviewer` precedent — all existing
construction sites stay valid), storage on `ExecutionOrchestrator`,
and composition-root wiring where the container composes the REAL guard
(real IConfigService + time.monotonic) into the ports factory.
"""

import time
from typing import Optional, cast
from unittest.mock import Mock

import pytest

from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.execution_report_assembler import (
    IExecutionReportAssembler,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.utils.interrupt_guard import InterruptGuard


def _build_ports(interrupt_guard: Optional[InterruptGuard] = None) -> OrchestratorPorts:
    """OrchestratorPorts with spec-bound doubles for the required fields.

    Each double is cast to its port protocol at the construction site:
    Mypy cannot type-check a dict unpack (**defaults) against the DTO's
    typed keyword parameters, so the explicit keyword construction with
    casts keeps the DTO construction Mypy-clean.
    """
    return OrchestratorPorts(
        plan_parser=cast(IPlanParser, Mock(spec=IPlanParser)),
        plan_validator=cast(IPlanValidator, Mock(spec=IPlanValidator)),
        action_executor=cast(ActionExecutor, Mock(spec=ActionExecutor)),
        file_system_manager=cast(IFileSystemManager, Mock(spec=IFileSystemManager)),
        report_assembler=cast(
            IExecutionReportAssembler, Mock(spec=IExecutionReportAssembler)
        ),
        user_interactor=cast(IUserInteractor, Mock(spec=IUserInteractor)),
        interrupt_guard=interrupt_guard,
    )


@pytest.fixture
def guard() -> InterruptGuard:
    """A REAL InterruptGuard over a spec-bound config double.

    The real constructor exercises the documented config read path
    (get_setting("interrupt.grace_window_seconds", 2.0)) so the storage
    tests inject a genuine guard instance, not a mock stand-in.
    """
    config = Mock(spec=IConfigService)
    config.get_setting.return_value = 2.0
    return InterruptGuard(config_service=config, monotonic=time.monotonic)


class TestOrchestratorPortsInterruptGuardSeam:
    """The optional interrupt_guard field on the OrchestratorPorts DTO."""

    def test_interrupt_guard_field_defaults_to_none(self) -> None:
        # Act
        ports = _build_ports()

        # Assert: the optional field preserves every existing construction
        # site (green-to-green) — no guard supplied means None.
        assert ports.interrupt_guard is None

    def test_ports_accept_injected_interrupt_guard(self, guard: InterruptGuard) -> None:
        # Act
        ports = _build_ports(interrupt_guard=guard)

        # Assert
        assert ports.interrupt_guard is guard


class TestExecutionOrchestratorGuardStorage:
    """The orchestrator stores the guard delivered via the ports DTO."""

    def test_orchestrator_stores_injected_interrupt_guard(
        self, guard: InterruptGuard
    ) -> None:
        # Arrange
        ports = _build_ports(interrupt_guard=guard)

        # Act
        orchestrator = ExecutionOrchestrator(ports=ports)

        # Assert
        assert orchestrator._interrupt_guard is guard

    def test_orchestrator_defaults_to_none_without_guard(self) -> None:
        # Arrange: the backward-compatibility construction (no guard).
        ports = _build_ports()

        # Act
        orchestrator = ExecutionOrchestrator(ports=ports)

        # Assert: absence of a guard must not break existing sites.
        assert orchestrator._interrupt_guard is None


class TestContainerGuardWiring:
    """The composition root composes the REAL guard into the ports DTO."""

    def test_container_ports_carry_real_interrupt_guard(self, container) -> None:
        # Act
        ports = container.resolve(OrchestratorPorts)

        # Assert: a genuine InterruptGuard (real IConfigService +
        # time.monotonic composed in container.py), not None and not a mock.
        assert isinstance(ports.interrupt_guard, InterruptGuard)

    def test_container_orchestrator_receives_real_interrupt_guard(
        self, container
    ) -> None:
        # Act
        orchestrator = container.resolve(ExecutionOrchestrator)

        # Assert: the resolved orchestrator holds a real guard instance.
        assert isinstance(orchestrator._interrupt_guard, InterruptGuard)
