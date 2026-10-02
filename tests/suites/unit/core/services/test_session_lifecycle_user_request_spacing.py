"""Regression: `resume -m` appends `## User Request` with a blank-line separator.

Bug 55 (5a): `SessionLifecycleManager._append_user_request` concatenated the
section with a single leading newline. Because `finalize_turn` persists a
`.strip()`ed report (no trailing newline), the appended `## User Request`
heading was NOT preceded by a blank line. The fix strips the body's trailing
newlines and prepends exactly one blank line.
"""

from unittest.mock import create_autospec

import pytest

from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import register_mock

SESSION_ROOT = ".teddy/sessions/20260417_120000-feature"
TURN02 = f"{SESSION_ROOT}/02"
MESSAGE = "Tell me a joke"


@pytest.fixture
def manager(container):
    """SessionLifecycleManager with auto-specced port doubles."""
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
    )
    return SessionLifecycleManager(ports=ports)


def _orchestrator_with_report():
    orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    orchestrator.execute.return_value = create_autospec(ExecutionReport, instance=True)
    return orchestrator


def _arrange_empty_turn(manager, turn_path: str) -> None:
    """Classification: the fresh successor turn is EMPTY."""
    manager._session_service.get_session_state.side_effect = [
        (SessionState.EMPTY, turn_path),
        (SessionState.PENDING_PLAN, turn_path),
    ]
    manager._session_planner.trigger_new_plan.return_value = ("feature", None)
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{turn_dir}/{filename}"
    )


class TestUserRequestAppendSpacing:
    """The appended section is always preceded by exactly one blank line."""

    def test_append_inserts_blank_line_when_body_has_no_trailing_newline(
        self, manager
    ) -> None:
        # Arrange: the persisted report body has NO trailing newline, as
        # `finalize_turn` writes a `.strip()`ed report.
        _arrange_empty_turn(manager, TURN02)
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = (
            "# Report\n\n- **Overall Status:** SUCCESS"
        )
        orchestrator = _orchestrator_with_report()

        # Act
        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=MESSAGE,
        )

        # Assert: the heading is preceded by a blank line.
        written = manager._file_system_manager.write_file.call_args.args[1]
        assert "\n\n## User Request\n" in written
        heading_index = written.index("## User Request")
        assert written[:heading_index].endswith("\n\n")

    def test_append_adds_exactly_one_blank_line_when_body_ends_in_newline(
        self, manager
    ) -> None:
        # Arrange: a body already ending in a newline must not acquire
        # extra blank lines (the rstrip is idempotent).
        _arrange_empty_turn(manager, TURN02)
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        orchestrator = _orchestrator_with_report()

        # Act
        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=MESSAGE,
        )

        # Assert: exactly one blank line separates body from heading.
        written = manager._file_system_manager.write_file.call_args.args[1]
        assert "Prior report body\n\n## User Request\n" in written
        assert "Prior report body\n\n\n## User Request\n" not in written
