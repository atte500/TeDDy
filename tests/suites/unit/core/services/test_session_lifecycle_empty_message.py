"""Unit tests: EMPTY-state injected-message consumption in `resume`.

A completed session's latest turn is EMPTY after finalization (the
finalization pre-creates the initialized successor). Resuming such a
session with an injected message (`teddy resume -m`) must skip the
interactive prompt, plan the fresh turn with the injected message, and
append a smart-fenced `## User Request` section to the PREVIOUS
completed turn's report (the latest turn carrying report.md, discovered
by numeric sibling decrement). At turn 01 there is no previous report:
the message still drives planning, with no append and no crash.
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
TURN01 = f"{SESSION_ROOT}/01"
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
    """Classification: the fresh successor turn is EMPTY.

    Two get_session_state calls occur in the flow: the resume-top
    classification and the post-planning turn re-resolution.
    """
    manager._session_service.get_session_state.side_effect = [
        (SessionState.EMPTY, turn_path),
        (SessionState.PENDING_PLAN, turn_path),
    ]
    manager._session_planner.trigger_new_plan.return_value = ("feature", None)
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{turn_dir}/{filename}"
    )


class TestEmptyStateMessageResume:
    """An EMPTY turn resumed with an injected message plans, never prompts."""

    def test_injected_message_plans_and_appends_to_previous_report(
        self, manager
    ) -> None:
        # Arrange: turn 02 is EMPTY; turn 01 carries the completed report.
        _arrange_empty_turn(manager, TURN02)
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=MESSAGE,
        )

        # Assert: the injected message drives planning — no interactive
        # prompt, and the planner receives the message verbatim.
        manager._user_interactor.ask_question.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message=MESSAGE
        )
        # Assert: the PREVIOUS completed turn's report carries the
        # smart-fenced User Request section (identical _append_user_request
        # format: heading + ```text opening fence + bare closing fence).
        manager._file_system_manager.write_file.assert_called_once()
        written_path = str(manager._file_system_manager.write_file.call_args.args[0])
        assert written_path.endswith("01/report.md"), written_path
        expected = (
            "Prior report body\n\n## User Request\n```text\nTell me a joke\n```\n"
        )
        assert manager._file_system_manager.write_file.call_args.args[1] == expected
        # Assert: execution still targets the fresh turn's plan.
        executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
        assert TURN02 in executed_plan
        assert result[0] == "feature"

    def test_empty_turn_01_with_message_plans_without_append(self, manager) -> None:
        # Arrange: the very first turn is EMPTY — there is no previous
        # completed report to append to.
        _arrange_empty_turn(manager, TURN01)
        manager._file_system_manager.path_exists.return_value = False
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            message=MESSAGE,
        )

        # Assert: no append, no crash — planning still carries the message.
        manager._file_system_manager.write_file.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN01, message=MESSAGE
        )
        assert result[0] == "feature"
