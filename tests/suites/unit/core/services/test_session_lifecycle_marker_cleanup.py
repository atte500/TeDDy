"""Unit tests: finalizing a turn clears the in-flight execution marker.

``execution.started`` distinguishes a session turn that began dispatching
actions from one whose plan was written but never ran. That distinction only
matters while the turn has no report, so finalization removes the marker AFTER
writing ``report.md``: a kill between the two leaves a stale marker that no
resume path ever reads, because ``get_session_state`` resolves
``COMPLETE_TURN`` from the report first.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from unittest.mock import Mock

from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
)
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.domain.models.report_assembly_data import ReportAssemblyData
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import (
    EXECUTION_STARTED_MARKER,
    ISessionManager,
)
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import (
    path_exists_marker_absent,
    path_exists_marker_present,
    register_mock,
)

TURN03 = ".teddy/sessions/20261002_152331-follow-up/03"
PLAN_PATH = f"{TURN03}/plan.md"
REPORT_PATH = f"{TURN03}/report.md"
MARKER_PATH = f"{TURN03}/{EXECUTION_STARTED_MARKER}"
NEXT_TURN = ".teddy/sessions/20261002_152331-follow-up/04"
START_TIME = datetime(2026, 10, 2, 15, 23, 31, tzinfo=timezone.utc)


def _build_manager(container) -> SessionLifecycleManager:
    """SessionLifecycleManager with auto-specced port doubles.

    The report formatter returns a fixed body while the session service fixes
    the root-relative report path and the successor turn, so each test observes
    only the finalization side effects it asserts on.
    """
    time_service = cast(ITimeService, Mock(spec=ITimeService))
    time_service.now_utc.return_value = START_TIME
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
        plan_parser=cast(IPlanParser, Mock(spec=IPlanParser)),
        time_service=time_service,
        report_assembler=ExecutionReportAssembler(),
    )
    manager = SessionLifecycleManager(ports=ports)
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{Path(turn_dir).as_posix()}/{filename}"
    )
    manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
    manager._report_formatter.format.return_value = "# Execution Report\n"
    return manager


def _finalized_report() -> ExecutionReport:
    """A real assembled report, so finalization formats a genuine domain object."""
    plan = Plan(
        title="Follow-up",
        rationale="Action turn",
        actions=[ActionData(type="EXECUTE", params={"command": "echo 1"})],
    )
    return ExecutionReportAssembler().assemble(
        ReportAssemblyData(
            plan=plan,
            action_logs=[
                ActionLog(
                    status=ActionStatus.SUCCESS,
                    action_type="EXECUTE",
                    params={"command": "echo 1"},
                    details="ok",
                )
            ],
            start_time=START_TIME,
            is_session=True,
        )
    )


def test_finalization_writes_the_report_before_clearing_the_marker(container) -> None:
    events: list[tuple[str, str]] = []
    manager = _build_manager(container)
    file_system = manager._file_system_manager
    file_system.path_exists.side_effect = path_exists_marker_present(default=False)
    file_system.write_file.side_effect = lambda path, _content: events.append(
        ("write", path)
    )
    file_system.remove_path.side_effect = lambda path: events.append(("remove", path))

    manager.finalize_turn(PLAN_PATH, _finalized_report())

    assert events == [("write", REPORT_PATH), ("remove", MARKER_PATH)], events


def test_finalization_of_an_unmarked_turn_removes_nothing(container) -> None:
    manager = _build_manager(container)
    file_system = manager._file_system_manager
    file_system.path_exists.side_effect = path_exists_marker_absent(default=False)

    manager.finalize_turn(PLAN_PATH, _finalized_report())

    file_system.remove_path.assert_not_called()
    file_system.find_call_by_path("write_file", REPORT_PATH)
