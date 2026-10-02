"""Unit tests: reply-driven finalization in `_consume_awaiting_reply`.

The locked consumption design (user-approved): a reply on an
awaiting-reply turn (pipeline MESSAGE turn stopped before
finalization) must FINALIZE the interrupted turn — synthesizing the
standard message-turn report from its plan via the Constructor-Injected
plan parser and time service, writing `report.md` through
`finalize_turn` (NO `## User Request` section: the consumption path
never appends — the interrupted turn has no prior report) — then clear
the `awaiting_reply` flag and plan+execute the next turn with the
reply. This applies across ALL resume modes (pipeline or not).
"""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock, create_autospec

import pytest

from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import register_mock

AWAITING_TURN = ".teddy/sessions/20260417_120000-feature/01"
NEXT_TURN = ".teddy/sessions/20260417_120000-feature/02"
REPLY = "I am great, tell me a joke"
AGENT_MESSAGE = "Hi there! How are you doing today?"
PLAN_CONTENT = "# Greet User and Check In\n\n## Action Plan\n\n### MESSAGE\n..."
META_CONTENT = "agent_name: assistant\nturn_cost: 0.25\n"
FORMATTED_REPORT = (
    "# Execution Report: Greet User and Check In\n\n## Action Log\n\n"
    "### `MESSAGE`\n- **User Reply:**\n```\n" + AGENT_MESSAGE + "\n```\n"
)


@pytest.fixture
def manager(container):
    """SessionLifecycleManager with auto-specced port doubles plus the
    consumption doubles riding the Seam's optional ports."""
    plan_parser = cast(IPlanParser, Mock(spec=IPlanParser))
    plan_parser.parse.return_value = Plan(
        title="Greet User and Check In",
        rationale="Communication turn",
        actions=[
            ActionData(
                type="MESSAGE",
                # Mirrors the production parser reality: parse_message_action
                # writes params={"content": content} (action_parser_complex).
                params={"content": AGENT_MESSAGE},
                description="Message to user",
            )
        ],
    )
    time_service = cast(ITimeService, Mock(spec=ITimeService))
    time_service.now.return_value = datetime(2026, 10, 2, 12, 0, 0)
    time_service.now_utc.return_value = datetime(
        2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc
    )
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
        plan_parser=plan_parser,
        time_service=time_service,
    )
    return SessionLifecycleManager(ports=ports)


def _orchestrator_with_report():
    orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    orchestrator.execute.return_value = create_autospec(ExecutionReport, instance=True)
    return orchestrator


def _arrange_awaiting_reply(manager) -> None:
    """Classification: plan.md present, report.md absent (PENDING_PLAN).

    The awaiting turn's meta carries the flag; the interrupted plan's
    markdown is read via path-keyed read_file (finalize_turn's meta read
    must see the meta yaml, not the plan markdown).
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
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{turn_dir}/{filename}"
    )
    manager._file_system_manager.path_exists.side_effect = lambda path: str(
        path
    ).endswith("meta.yaml")
    manager._file_system_manager.read_file.side_effect = lambda path: (
        PLAN_CONTENT if str(path).endswith("plan.md") else META_CONTENT
    )
    manager._report_formatter.format.return_value = FORMATTED_REPORT
    manager._session_planner.trigger_new_plan.return_value = ("feature", None)


def test_reply_finalizes_awaiting_turn_then_plans_next_turn(manager) -> None:
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

    # Assert: the interrupted plan was parsed for the synthesis.
    manager._plan_parser.parse.assert_called_once()
    # Assert: the synthesized report carries the agent's MESSAGE log —
    # the standard message-turn shape extracted from the parsed plan.
    manager._report_formatter.format.assert_called_once()
    synthesized = manager._report_formatter.format.call_args.args[0]
    message_logs = [
        log for log in synthesized.action_logs if log.action_type == "MESSAGE"
    ]
    assert len(message_logs) == 1
    assert AGENT_MESSAGE in (message_logs[0].details or "")
    # Assert: the interrupted turn is FINALIZED — the standard message-turn
    # report lands at 01/report.md with NO ## User Request section (locked
    # design: the append applies only when a prior report already exists).
    manager._file_system_manager.write_file.assert_called_once()
    written_path = str(manager._file_system_manager.write_file.call_args.args[0])
    assert written_path.endswith("01/report.md"), written_path
    written_content = manager._file_system_manager.write_file.call_args.args[1]
    assert written_content == FORMATTED_REPORT
    assert "## User Request" not in written_content
    # Assert: the awaiting_reply flag is stripped from the turn meta.
    save_call = manager._session_service.save_turn_meta.call_args
    assert save_call is not None
    assert "awaiting_reply" not in save_call.args[1]
    # Assert: the transition carries the synthesized report (finalize_turn).
    transition_call = manager._session_service.transition_to_next_turn.call_args
    assert transition_call.kwargs.get("execution_report") is synthesized
    # Assert: turn 02 is planned from the injected reply and executed —
    # no interactive prompt on the injected-reply path.
    manager._user_interactor.ask_question.assert_not_called()
    manager._session_planner.trigger_new_plan.assert_called_once_with(
        NEXT_TURN, message=REPLY
    )
    executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
    assert NEXT_TURN in executed_plan
    assert result[0] == "feature"
