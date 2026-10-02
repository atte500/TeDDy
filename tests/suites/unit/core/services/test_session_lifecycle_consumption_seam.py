"""Unit tests: consumption-seam expansion on SessionPorts.

Drives the non-breaking seam expansion arming the reply-driven
consumption deliverables: additive optional `plan_parser` and
`time_service` fields on the frozen `SessionPorts` DTO (mirroring the
optional-field precedent — all existing construction sites stay valid),
storage on `SessionLifecycleManager`, and composition-root wiring where
the container resolves the REAL implementations into the ports factory.
"""

from typing import Optional, cast
from unittest.mock import Mock

import pytest

from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import register_mock


def _build_ports(
    plan_parser: Optional[IPlanParser] = None,
    time_service: Optional[ITimeService] = None,
) -> SessionPorts:
    """SessionPorts with spec-bound doubles for the required fields.

    Each double is cast to its port protocol at the construction site
    (the sanctioned test-file idiom for DTO construction under Mypy).
    """
    return SessionPorts(
        session_service=cast(ISessionManager, Mock(spec=ISessionManager)),
        file_system_manager=cast(IFileSystemManager, Mock(spec=IFileSystemManager)),
        report_formatter=cast(
            IMarkdownReportFormatter, Mock(spec=IMarkdownReportFormatter)
        ),
        user_interactor=cast(IUserInteractor, Mock(spec=IUserInteractor)),
        session_planner=cast(SessionPlanner, Mock(spec=SessionPlanner)),
        replanner=cast(SessionReplanner, Mock(spec=SessionReplanner)),
        plan_parser=plan_parser,
        time_service=time_service,
    )


class TestSessionPortsConsumptionFields:
    """Additive optional fields on the frozen SessionPorts DTO."""

    def test_consumption_fields_default_to_none(self) -> None:
        # Act
        ports = _build_ports()

        # Assert: the optional fields preserve every existing construction
        # site (green-to-green) — unsupplied means None.
        assert ports.plan_parser is None
        assert ports.time_service is None

    def test_ports_accept_injected_plan_parser_and_time_service(self) -> None:
        # Arrange
        parser = cast(IPlanParser, Mock(spec=IPlanParser))
        time_service = cast(ITimeService, Mock(spec=ITimeService))

        # Act
        ports = _build_ports(plan_parser=parser, time_service=time_service)

        # Assert
        assert ports.plan_parser is parser
        assert ports.time_service is time_service


class TestLifecycleManagerStorage:
    """The lifecycle manager stores the injected consumption fields."""

    @pytest.fixture
    def ports(self, container) -> SessionPorts:
        """SessionPorts over register_mock autospecs plus the injected
        consumption doubles."""
        return SessionPorts(
            session_service=register_mock(container, ISessionManager),
            file_system_manager=register_mock(container, IFileSystemManager),
            report_formatter=register_mock(container, IMarkdownReportFormatter),
            user_interactor=register_mock(container, IUserInteractor),
            session_planner=register_mock(container, SessionPlanner),
            replanner=register_mock(container, SessionReplanner),
            plan_parser=cast(IPlanParser, Mock(spec=IPlanParser)),
            time_service=cast(ITimeService, Mock(spec=ITimeService)),
        )

    def test_manager_stores_injected_plan_parser_and_time_service(
        self, ports: SessionPorts
    ) -> None:
        # Act
        manager = SessionLifecycleManager(ports=ports)

        # Assert: the consumption Logic deliverables consume the injected
        # parser and time service through the manager's stored fields.
        assert manager._plan_parser is ports.plan_parser
        assert manager._time_service is ports.time_service


class TestContainerSessionPortsWiring:
    """The composition root wires the REAL implementations."""

    def test_container_ports_carry_real_plan_parser(self, container) -> None:
        # Act
        ports = container.resolve(SessionPorts)

        # Assert: a genuine MarkdownPlanParser (the registered IPlanParser
        # implementation), not None and not a mock.
        assert isinstance(ports.plan_parser, MarkdownPlanParser)

    def test_container_ports_carry_real_time_service(self, container) -> None:
        # Act
        ports = container.resolve(SessionPorts)

        # Assert: the container-resolved time service exposes the
        # ITimeService surface (now / now_utc) the report synthesis uses.
        assert ports.time_service is not None
        assert hasattr(ports.time_service, "now")
        assert hasattr(ports.time_service, "now_utc")
