"""Unit tests: AWAITING_REPLY state machine in `SessionLifecycleManager.resume`.

A pipeline MESSAGE turn ends with `plan.md`, NO `report.md`, and
`awaiting_reply: true` in the turn meta. `get_session_state` classifies
that turn as PENDING_PLAN, which would wrongly RE-EXECUTE the message
plan. The state machine must consult the meta flag at the top of
`resume`: the awaiting turn is consumed (flag cleared via the
session-manager port), the session transitions to the next turn, and
planning receives the user's reply — injected via `resume -m` or
prompted interactively (mirroring the abort flow). Non-awaiting turns
keep the exact existing resume behavior.
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
from teddy_executor.core.utils.markdown import get_fence_for_content
from tests.harness.setup.mocking import register_mock

AWAITING_TURN = ".teddy/sessions/20260417_120000-feature/01"
NEXT_TURN = ".teddy/sessions/20260417_120000-feature/02"
REPLY = "I am great, tell me a joke"


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


def _arrange_awaiting_reply(manager) -> None:
    """Classification: plan.md present, report.md absent (PENDING_PLAN).

    Two get_session_state calls occur in the consumed flow: the resume-top
    classification and the post-planning turn re-resolution.
    """
    manager._session_service.get_session_state.side_effect = [
        (SessionState.PENDING_PLAN, AWAITING_TURN),
        (SessionState.PENDING_PLAN, NEXT_TURN),
    ]
    manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
    manager._session_service.load_turn_meta.return_value = {
        "agent_name": "assistant",
        "awaiting_reply": True,
    }
    manager._session_planner.trigger_new_plan.return_value = ("feature", None)


class TestAwaitingReplyStateMachine:
    """An awaiting-reply turn must be consumed, never re-executed."""

    def test_injected_message_clears_flag_transitions_and_plans(self, manager) -> None:
        # Arrange
        _arrange_awaiting_reply(manager)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            message=REPLY,
        )

        # Assert: the awaiting turn's plan is NOT re-executed — execution
        # targets the NEXT turn's plan produced from the injected reply.
        executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
        assert NEXT_TURN in executed_plan
        assert AWAITING_TURN not in executed_plan
        # The flag is cleared on the awaiting turn's meta (load-modify-save).
        manager._session_service.save_turn_meta.assert_called_once_with(
            AWAITING_TURN, {"agent_name": "assistant"}
        )
        # The session transitions before planning the reply.
        manager._session_service.transition_to_next_turn.assert_called_once_with(
            plan_path=f"{AWAITING_TURN}/plan.md"
        )
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            NEXT_TURN, message=REPLY
        )
        assert result[0] == "feature"

    def test_interactive_resume_prompts_for_reply_and_consumes_it(
        self, manager
    ) -> None:
        # Arrange
        _arrange_awaiting_reply(manager)
        manager._user_interactor.ask_question.return_value = "my prompted reply"
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
        )

        # Assert: mirrors the abort flow — prompt for the reply, then plan.
        manager._user_interactor.ask_question.assert_called_once()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            NEXT_TURN, message="my prompted reply"
        )
        executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
        assert NEXT_TURN in executed_plan
        assert result[0] == "feature"

    def test_interactive_empty_reply_terminates_without_consumption(
        self, manager
    ) -> None:
        # Arrange
        _arrange_awaiting_reply(manager)
        manager._user_interactor.ask_question.return_value = ""
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
        )

        # Assert: empty reply = terminate (abort-flow idiom). The session
        # stays in its awaiting state — the flag is NOT cleared.
        assert result == ("feature", None)
        orchestrator.execute.assert_not_called()
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_service.save_turn_meta.assert_not_called()

    def test_non_interactive_without_message_exits_cleanly_with_guidance(
        self, manager
    ) -> None:
        # Arrange
        _arrange_awaiting_reply(manager)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
        )

        # Assert: clean exit with guidance; nothing consumed or executed.
        assert result == ("feature", None)
        manager._user_interactor.display_message.assert_called_once()
        orchestrator.execute.assert_not_called()
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_not_called()
        manager._session_service.save_turn_meta.assert_not_called()

    def test_pending_plan_without_flag_still_reexecutes_existing_behavior(
        self, manager
    ) -> None:
        # Arrange: an interrupted (non-pipeline) turn — plan, no report,
        # NO awaiting_reply flag — must keep the exact existing behavior.
        manager._session_service.get_session_state.return_value = (
            SessionState.PENDING_PLAN,
            AWAITING_TURN,
        )
        manager._session_service.load_turn_meta.return_value = {
            "agent_name": "assistant"
        }
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
        )

        # Assert: the plan is re-executed in place (pre-existing contract).
        orchestrator.execute.assert_called_once_with(
            plan_path=f"{AWAITING_TURN}/plan.md",
            interactive=False,
            project_context=None,
            pipeline=False,
        )
        manager._session_service.save_turn_meta.assert_not_called()
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_not_called()
        assert result[0] == "feature"


class TestCompleteTurnMessageResume:
    """COMPLETE_TURN resume with an injected message must skip the prompt."""

    def test_injected_message_skips_prompt_and_plans_with_message(
        self, manager
    ) -> None:
        # Arrange
        manager._session_service.get_session_state.side_effect = [
            (SessionState.COMPLETE_TURN, AWAITING_TURN),
            (SessionState.PENDING_PLAN, NEXT_TURN),
        ]
        manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
        manager._session_planner.trigger_new_plan.return_value = ("feature", None)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message="new request",
        )

        # Assert: NO interactive prompt; the message reaches planning.
        manager._user_interactor.ask_question.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            NEXT_TURN, message="new request"
        )
        assert result[0] == "feature"


class TestCompleteTurnUserRequestAppend:
    """COMPLETE_TURN + -m appends a smart-fenced `## User Request` section.

    The section is appended to the latest turn's report.md BEFORE the
    transition, matching the execution_report.md.j2 User Request format
    (heading + smart-fenced codeblock; the opening fence carries the
    "text" language suffix, the closing fence is bare) so
    session_service's `^## User Request` detection regex recognizes the
    turn as a user-request turn.
    """

    def test_appends_user_request_section_to_latest_report(self, manager) -> None:
        # Arrange
        existing_report = "# Turn 1 Report\n\nAll actions succeeded.\n"
        manager._session_service.get_session_state.side_effect = [
            (SessionState.COMPLETE_TURN, AWAITING_TURN),
            (SessionState.PENDING_PLAN, NEXT_TURN),
        ]
        manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
        manager._session_service.to_root_relative.return_value = (
            f"{AWAITING_TURN}/report.md"
        )
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = existing_report
        manager._session_planner.trigger_new_plan.return_value = ("feature", None)
        orchestrator = _orchestrator_with_report()

        # Act
        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message="new request",
        )

        # Assert: the report is rewritten with the appended section.
        fence = get_fence_for_content("new request")
        expected = existing_report + (
            f"\n## User Request\n{fence}text\nnew request\n{fence}\n"
        )
        manager._file_system_manager.write_file.assert_called_once_with(
            f"{AWAITING_TURN}/report.md", expected
        )

    def test_append_lands_before_transition_to_next_turn(self, manager) -> None:
        # Arrange
        order: list[str] = []

        def _record_write(*args, **kwargs):
            order.append("write")

        def _record_transition(*args, **kwargs):
            order.append("transition")
            return NEXT_TURN

        manager._file_system_manager.write_file.side_effect = _record_write
        manager._session_service.transition_to_next_turn.side_effect = (
            _record_transition
        )
        manager._session_service.get_session_state.side_effect = [
            (SessionState.COMPLETE_TURN, AWAITING_TURN),
            (SessionState.PENDING_PLAN, NEXT_TURN),
        ]
        manager._session_service.to_root_relative.return_value = (
            f"{AWAITING_TURN}/report.md"
        )
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = "# Report\n"
        manager._session_planner.trigger_new_plan.return_value = ("feature", None)
        orchestrator = _orchestrator_with_report()

        # Act
        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message="new request",
        )

        # Assert: the report rewrite precedes the turn transition.
        assert order == ["write", "transition"]

    def test_append_smart_fence_escalates_for_nested_backtick_runs(
        self, manager
    ) -> None:
        # Arrange
        message = "Use `code` and ```fenced``` blocks here"
        existing_report = "# Report\n"
        manager._session_service.get_session_state.side_effect = [
            (SessionState.COMPLETE_TURN, AWAITING_TURN),
            (SessionState.PENDING_PLAN, NEXT_TURN),
        ]
        manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
        manager._session_service.to_root_relative.return_value = (
            f"{AWAITING_TURN}/report.md"
        )
        manager._file_system_manager.path_exists.return_value = True
        manager._file_system_manager.read_file.return_value = existing_report
        manager._session_planner.trigger_new_plan.return_value = ("feature", None)
        orchestrator = _orchestrator_with_report()

        # Act
        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
            message=message,
        )

        # Assert: fence length = longest backtick run in the message + 1.
        fence = get_fence_for_content(message)
        assert fence == "````"
        expected = existing_report + (
            f"\n## User Request\n{fence}text\n{message}\n{fence}\n"
        )
        manager._file_system_manager.write_file.assert_called_once_with(
            f"{AWAITING_TURN}/report.md", expected
        )

    def test_resume_without_message_does_not_touch_report(self, manager) -> None:
        # Arrange: COMPLETE_TURN resume WITHOUT an injected message.
        manager._session_service.get_session_state.side_effect = [
            (SessionState.COMPLETE_TURN, AWAITING_TURN),
            (SessionState.PENDING_PLAN, NEXT_TURN),
        ]
        manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
        manager._session_planner.trigger_new_plan.return_value = ("feature", None)
        orchestrator = _orchestrator_with_report()

        # Act
        manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=True,
        )

        # Assert: the existing report is left untouched.
        manager._file_system_manager.write_file.assert_not_called()
