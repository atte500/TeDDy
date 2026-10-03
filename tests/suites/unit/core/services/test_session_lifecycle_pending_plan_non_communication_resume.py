"""Unit tests: resume -m on a NON-communication PENDING_PLAN turn must
honor the injected reply instead of dropping it on a bare re-execution.

Bug 60: the PENDING_PLAN non-communication branch of
SessionLifecycleManager.resume called orchestrator.execute(plan_path=...)
WITHOUT threading the injected message -- the ONLY dispatch site in the
resume state machine that discarded a `-m` reply (Bug 57 fixed only the
COMMUNICATION sub-branch via _consume_awaiting_reply). For a normal pending
turn (plan.md present, report.md absent, no awaiting_reply flag), the reply
vanished: no user-request section, no TUI seed. The fix parses the pending
plan WITH its plan_path (preserving Plan.is_session / Plan.plan_path),
seeds plan.metadata["user_request"] = message, and calls
orchestrator.execute(plan=plan, plan_path=plan_path, ...) WITHOUT message=
(a forwarded message would WIN in the report assembler over
plan.metadata["user_request"] and discard a TUI harvest). An unparseable
pending plan falls back to the existing re-execute path.

Controls pinned here (must stay green): a resume with NO injected reply
re-executes the pending turn unchanged, and an unparseable pending plan
degrades gracefully to that same re-execute path.
"""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock, create_autospec

import pytest

from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
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

TURN03 = ".teddy/sessions/20261002_152331-follow-up/03"
REPLY = "next instruction"
PLAN_PATH = f"{TURN03}/plan.md"


def _action_plan() -> Plan:
    """A non-communication turn (single EXECUTE action)."""
    return Plan(
        title="Follow-up",
        rationale="Action turn",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo 1"},
                description="Do something",
            )
        ],
    )


def _build_manager(container, plan: Plan) -> SessionLifecycleManager:
    """SessionLifecycleManager with auto-specced port doubles.

    The injected plan parser returns the supplied plan; the injected time
    service returns a real timestamp so any future report assembly sees a
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


def _arrange_pending_action_turn(manager) -> None:
    """The user's state: plan.md present, report.md absent, NO flag."""
    manager._session_service.get_session_state.return_value = (
        SessionState.PENDING_PLAN,
        TURN03,
    )
    manager._session_service.load_turn_meta.return_value = {"agent_name": "assistant"}


class TestPendingPlanNonCommunicationResume:
    """An injected reply on a pending ACTION turn must be honored (seeded)."""

    @pytest.mark.parametrize("interactive", [True, False])
    def test_injected_reply_seeds_plan_and_executes_parsed_plan(
        self, container, interactive: bool
    ) -> None:
        # Arrange: a normal pending plan (single EXECUTE action), NO awaiting_reply.
        plan = _action_plan()
        manager = _build_manager(container, plan)
        _arrange_pending_action_turn(manager)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            interactive=interactive,
            message=REPLY,
        )

        # Assert: the pending plan was parsed WITH its plan_path (path precision).
        manager._plan_parser.parse.assert_called_once()
        assert manager._plan_parser.parse.call_args.kwargs.get("plan_path") == PLAN_PATH
        # Assert: the injected reply is seeded onto the plan's metadata.
        assert plan.metadata.get("user_request") == REPLY
        # Assert: the SEEDED plan is executed in place, WITHOUT message=.
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs.get("plan") is plan
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert "message" not in execute_kwargs
        # Assert: no interactive re-prompt and no transition/planning here.
        manager._user_interactor.ask_question.assert_not_called()
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_not_called()
        assert result[0] == "follow-up"

    def test_no_message_reexecutes_unchanged(self, container) -> None:
        # Arrange: NO injected reply -- the pending turn is re-executed in place.
        plan = _action_plan()
        manager = _build_manager(container, plan)
        _arrange_pending_action_turn(manager)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            interactive=False,
        )

        # Assert: unchanged pre-existing behavior (bare re-execute, no seed).
        orchestrator.execute.assert_called_once()
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert execute_kwargs.get("plan") is None
        assert plan.metadata.get("user_request") is None
        assert result[0] == "follow-up"

    def test_unparseable_plan_falls_back_to_reexecute(self, container) -> None:
        # Arrange: the pending plan cannot be parsed.
        plan = _action_plan()
        manager = _build_manager(container, plan)
        manager._plan_parser.parse.side_effect = InvalidPlanError("bad plan")
        _arrange_pending_action_turn(manager)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            interactive=False,
            message=REPLY,
        )

        # Assert: graceful fallback to the re-execute path (no seed, no crash).
        orchestrator.execute.assert_called_once()
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert execute_kwargs.get("plan") is None
        assert result[0] == "follow-up"
