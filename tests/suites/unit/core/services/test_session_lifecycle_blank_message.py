"""Unit tests: present-but-blank injected message handling in `resume`.

`teddy resume -m ""` injects a present-but-blank message. In the EMPTY and
COMPLETE_TURN branches it must not seed a turn with no real instruction:
when a human is reachable (a terminal is attached and the run is not a
pipeline), the user is prompted for the next instruction (an empty reply
terminates the session, matching the abort idiom); otherwise it normalizes
to absent so the session resumes against context without blocking. Action
approval (`interactive`, False under yolo) MUST NOT suppress the prompt.
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
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
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
PROMPT = "What would you like to do next?"


@pytest.fixture
def manager(container):
    """SessionLifecycleManager with auto-specced port doubles.

    ``isatty()`` is pinned False so the manager sees no terminal by default;
    a test that models a human at the terminal flips it through
    ``manager._system_environment.isatty.return_value``.
    """
    system_environment = register_mock(container, ISystemEnvironment)
    system_environment.isatty.return_value = False
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
        system_environment=system_environment,
    )
    return SessionLifecycleManager(ports=ports)


def _orchestrator_with_report():
    orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    orchestrator.execute.return_value = create_autospec(ExecutionReport, instance=True)
    return orchestrator


def _arrange_state(manager, state, turn_path):
    """Classify the resume top as ``state`` and the post-planning turn as PENDING."""
    manager._session_service.get_session_state.side_effect = [
        (state, turn_path),
        (SessionState.PENDING_PLAN, turn_path),
    ]
    manager._session_planner.trigger_new_plan.return_value = ("feature", None)
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{turn_dir}/{filename}"
    )


class TestEmptyStateBlankMessage:
    """EMPTY-state present-but-blank message resolution."""

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_interactive_blank_message_prompts_and_plans(self, manager, blank):
        _arrange_state(manager, SessionState.EMPTY, TURN02)
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        manager._user_interactor.ask_question.return_value = "Tell me a joke"
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=blank,
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message="Tell me a joke"
        )
        assert result[0] == "feature"

    def test_interactive_blank_message_empty_reply_terminates(self, manager):
        _arrange_state(manager, SessionState.EMPTY, TURN02)
        manager._user_interactor.ask_question.return_value = ""
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message="",
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._session_planner.trigger_new_plan.assert_not_called()
        orchestrator.execute.assert_not_called()
        assert result == ("feature", None)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_message_without_a_terminal_resumes_without_prompt(
        self, manager, blank
    ):
        """No terminal attached: there is nobody to prompt."""
        _arrange_state(manager, SessionState.EMPTY, TURN02)
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            message=blank,
        )

        manager._user_interactor.ask_question.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message=None
        )
        assert result[0] == "feature"

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_yolo_blank_message_prompts_when_a_terminal_is_attached(
        self, manager, blank
    ):
        """Action approval off (yolo) MUST NOT suppress the prompt."""
        _arrange_state(manager, SessionState.EMPTY, TURN02)
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        manager._user_interactor.ask_question.return_value = "Tell me a joke"
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            message=blank,
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message="Tell me a joke"
        )
        assert result[0] == "feature"


class TestCompleteTurnBlankMessage:
    """COMPLETE_TURN present-but-blank message resolution."""

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_interactive_blank_message_prompts_and_plans(self, manager, blank):
        _arrange_state(manager, SessionState.COMPLETE_TURN, TURN01)
        manager._session_service.transition_to_next_turn.return_value = TURN02
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        manager._user_interactor.ask_question.return_value = "Next step"
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=blank,
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message="Next step"
        )
        assert result[0] == "feature"

    def test_interactive_blank_message_empty_reply_terminates(self, manager):
        _arrange_state(manager, SessionState.COMPLETE_TURN, TURN01)
        manager._user_interactor.ask_question.return_value = "   "
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message="",
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_not_called()
        assert result == ("feature", None)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_message_without_a_terminal_resumes_without_prompt(
        self, manager, blank
    ):
        """No terminal attached: there is nobody to prompt."""
        _arrange_state(manager, SessionState.COMPLETE_TURN, TURN01)
        manager._session_service.transition_to_next_turn.return_value = TURN02
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            message=blank,
        )

        manager._user_interactor.ask_question.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message=None
        )
        assert result[0] == "feature"

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_yolo_blank_message_prompts_when_a_terminal_is_attached(
        self, manager, blank
    ):
        """Action approval off (yolo) MUST NOT suppress the prompt."""
        _arrange_state(manager, SessionState.COMPLETE_TURN, TURN01)
        manager._session_service.transition_to_next_turn.return_value = TURN02
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        manager._user_interactor.ask_question.return_value = "Next step"
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            message=blank,
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message="Next step"
        )
        assert result[0] == "feature"


class TestNonBlankMessagesUnchanged:
    """Absent and non-blank messages keep their existing behavior."""

    def test_absent_message_never_prompts(self, manager):
        _arrange_state(manager, SessionState.COMPLETE_TURN, TURN01)
        manager._session_service.transition_to_next_turn.return_value = TURN02
        orchestrator = _orchestrator_with_report()

        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=None,
        )

        manager._user_interactor.ask_question.assert_not_called()

    def test_non_blank_message_skips_prompt(self, manager):
        _arrange_state(manager, SessionState.COMPLETE_TURN, TURN01)
        manager._session_service.transition_to_next_turn.return_value = TURN02
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "Prior report body\n"
        orchestrator = _orchestrator_with_report()

        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message="Real instruction",
        )

        manager._user_interactor.ask_question.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN02, message="Real instruction"
        )
