"""Unit tests: resume -m on a PENDING_PLAN COMMUNICATION turn without the
awaiting_reply flag must consume the injected reply (never re-execute).

Reproduces the reported symptom: a session whose latest turn is an
interactively-interrupted MESSAGE turn -- plan.md present, report.md
absent, and NO awaiting_reply flag (only the pipeline-stop path sets that
flag) -- is classified as PENDING_PLAN. Resuming it with an injected reply
must treat that reply as the awaited reply for the communication turn:
finalize the interrupted turn (standard message-turn report, no User
Request section) and plan/execute the NEXT turn from the reply. The
pre-fix behaviour re-executed the interrupted MESSAGE plan, DROPPED the
reply, and re-prompted the user.

A resume with NO injected reply must be unchanged. The NON-communication
PENDING_PLAN turn is covered by its own suite
(`test_session_lifecycle_pending_plan_non_communication_resume.py`); Bug 60
changed that branch to seed the injected reply onto the parsed pending plan
(before executing it) instead of dropping it.
"""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock, create_autospec

from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.planning_ports import SessionPorts
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
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import register_mock

TURN03 = ".teddy/sessions/20261002_152331-say-ask/03"
TURN04 = ".teddy/sessions/20261002_152331-say-ask/04"
REPLY = "hello"
AGENT_MESSAGE = "I'm ready for it - but you only sent 'new request'."
PLAN_CONTENT = "# Await New Request Details\n\n## Action Plan\n\n### MESSAGE\n..."
META_CONTENT = "agent_name: assistant\nturn_cost: 0.0\n"
FORMATTED_REPORT = "# Execution Report: Await New Request Details\n"


def _communication_plan() -> Plan:
    """A single-MESSAGE turn (Plan.is_communication_turn() == True)."""
    return Plan(
        title="Await New Request Details",
        rationale="Communication turn",
        actions=[
            ActionData(
                type="MESSAGE",
                params={"content": AGENT_MESSAGE},
                description="Message to user",
            )
        ],
    )


def _build_manager(container, plan: Plan) -> SessionLifecycleManager:
    """SessionLifecycleManager with auto-specced port doubles.

    The injected plan parser returns the supplied plan; the injected time
    service returns a real timestamp so the report assembler sees a
    deterministic start time.
    """
    plan_parser = cast(IPlanParser, Mock(spec=IPlanParser))
    plan_parser.parse.return_value = plan
    time_service = cast(ITimeService, Mock(spec=ITimeService))
    time_service.now.return_value = datetime(2026, 10, 2, 15, 23, 31)
    time_service.now_utc.return_value = datetime(
        2026, 10, 2, 15, 23, 31, tzinfo=timezone.utc
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
        report_assembler=ExecutionReportAssembler(),
    )
    return SessionLifecycleManager(ports=ports)


def _orchestrator_with_report():
    orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    orchestrator.execute.return_value = create_autospec(ExecutionReport, instance=True)
    return orchestrator


def _arrange_pending_communication_turn(manager) -> None:
    """The user's real state: plan.md present, report.md absent, NO flag.

    Two get_session_state calls occur on the consuming flow: the resume-top
    classification (turn 03) and the post-planning re-resolution (turn 04).
    read_file is path-keyed so the pending plan's markdown is returned for
    plan.md while finalize_turn's meta read still sees the meta yaml.
    """
    manager._session_service.get_session_state.side_effect = [
        (SessionState.PENDING_PLAN, TURN03),
        (SessionState.PENDING_PLAN, TURN04),
    ]
    manager._session_service.load_turn_meta.return_value = {"agent_name": "assistant"}
    manager._session_service.transition_to_next_turn.return_value = TURN04
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
    manager._session_planner.trigger_new_plan.return_value = ("say-ask", None)


class TestPendingPlanCommunicationResume:
    """An injected reply on a pending COMMUNICATION turn must be consumed."""

    def test_injected_reply_finalizes_turn_and_plans_next_turn(self, container) -> None:
        # Arrange: pending MESSAGE turn WITHOUT awaiting_reply (the user's state).
        manager = _build_manager(container, _communication_plan())
        _arrange_pending_communication_turn(manager)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="say-ask",
            orchestrator=orchestrator,
            interactive=True,
            message=REPLY,
        )

        # Assert: the reply reaches planning (it was NOT dropped).
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN04, message=REPLY
        )
        # Assert: the pending plan was parsed exactly ONCE on the resume
        # path (the single WITH-path parse is reused for the communication
        # decision AND the report synthesis -- no double-parse).
        manager._plan_parser.parse.assert_called_once()
        # Assert: the interrupted turn is FINALIZED -- the standard
        # message-turn report lands at 03/report.md via finalize_turn.
        manager._file_system_manager.write_file.assert_called_once()
        written_path = str(manager._file_system_manager.write_file.call_args.args[0])
        assert written_path.endswith("03/report.md"), written_path
        transition_call = manager._session_service.transition_to_next_turn.call_args
        assert transition_call.kwargs["plan_path"] == f"{TURN03}/plan.md"
        assert "execution_report" in transition_call.kwargs
        # Assert: NO interactive re-prompt (the reply was injected).
        manager._user_interactor.ask_question.assert_not_called()
        # Assert: the interrupted plan is NOT re-executed -- execution
        # targets the NEXT turn's plan, never the pending turn's plan.
        executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
        assert TURN04 in executed_plan
        assert TURN03 not in executed_plan
        assert result[0] == "say-ask"

    def test_resume_without_message_keeps_reexecute_behavior(self, container) -> None:
        # Arrange: no injected reply -- the pending turn is re-executed in place.
        manager = _build_manager(container, _communication_plan())
        manager._session_service.get_session_state.return_value = (
            SessionState.PENDING_PLAN,
            TURN03,
        )
        manager._session_service.load_turn_meta.return_value = {
            "agent_name": "assistant"
        }
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="say-ask",
            orchestrator=orchestrator,
            interactive=False,
        )

        # Assert: unchanged pre-existing behavior (no consumption, no prompt).
        orchestrator.execute.assert_called_once()
        executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
        assert TURN03 in executed_plan
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_not_called()
        manager._user_interactor.ask_question.assert_not_called()
        assert result[0] == "say-ask"
