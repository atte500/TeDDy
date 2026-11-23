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

An unparseable pending plan still re-executes WITHOUT a seeded plan, but the
reply is no longer dropped: once `execute` returns, the structural replan has
written the resumed turn's failure report, so the reply is appended to it as a
`## User Request` section and the turn is re-evaluated for preservation into
the prune-exempt `session.context`.

Controls pinned here (must stay green): a resume with NO injected reply
re-executes the pending turn unchanged, and an unparseable pending plan with
no report on disk degrades gracefully without recording anything.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from unittest.mock import Mock, create_autospec

import pytest

from teddy_executor.core.domain.models.execution_report import (
    ActionStatus,
    ExecutionReport,
    RunStatus,
)
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import (
    EXECUTION_STARTED_MARKER,
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
from tests.harness.setup.mocking import (
    path_exists_marker_absent,
    register_mock,
    to_posix_path,
)

TURN03 = ".teddy/sessions/20261002_152331-follow-up/03"
TURN04 = ".teddy/sessions/20261002_152331-follow-up/04"
REPLY = "next instruction"
PLAN_PATH = f"{TURN03}/plan.md"
REPORT_PATH = f"{TURN03}/report.md"
VALIDATION_REPORT = (
    "# Execution Report: Follow-up\n- **Overall Status:** Validation Failed\n"
)


def _marker_present(path: str) -> bool:
    """``path_exists`` double for a killed turn: only the marker exists."""
    return to_posix_path(path).rsplit("/", 1)[-1] == EXECUTION_STARTED_MARKER


def _arrange_marked_interrupted_turn(manager) -> None:
    """A hard-killed turn: plan.md plus execution.started, no report.md."""
    manager._session_service.get_session_state.side_effect = [
        (SessionState.PENDING_PLAN, TURN03),
        (SessionState.EMPTY, TURN04),
    ]
    manager._session_service.load_turn_meta.return_value = {"agent_name": "assistant"}
    manager._session_service.transition_to_next_turn.return_value = TURN04
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{Path(turn_dir).as_posix()}/{filename}"
    )
    manager._file_system_manager.path_exists.side_effect = _marker_present
    manager._file_system_manager.read_raw_file.return_value = "# plan"
    manager._report_formatter.format.return_value = "# Execution Report\n"
    manager._session_planner.trigger_new_plan.return_value = ("follow-up", None)


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
    file_system_manager = register_mock(container, IFileSystemManager)
    file_system_manager.path_exists.side_effect = path_exists_marker_absent()
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=file_system_manager,
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


def _arrange_resumed_turn_report(manager, present: bool) -> None:
    """The structural replan's report either exists or does not after execute."""
    manager._file_system_manager.path_exists.side_effect = path_exists_marker_absent(
        default=present
    )
    manager._file_system_manager.read_file.return_value = VALIDATION_REPORT
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{Path(turn_dir).as_posix()}/{filename}"
    )


class TestPendingPlanNonCommunicationResume:
    """An injected reply on a pending ACTION turn must be honored (seeded)."""

    @pytest.mark.parametrize("require_approval", [True, False])
    def test_injected_reply_seeds_plan_and_executes_parsed_plan(
        self, container, require_approval: bool
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
            require_approval=require_approval,
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
            require_approval=False,
        )

        # Assert: unchanged pre-existing behavior (bare re-execute, no seed).
        orchestrator.execute.assert_called_once()
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert execute_kwargs.get("plan") is None
        assert plan.metadata.get("user_request") is None
        assert result[0] == "follow-up"

    def test_unparseable_plan_records_reply_on_resumed_turn(self, container) -> None:
        # Arrange: the pending plan cannot be parsed; the replan wrote a report.
        plan = _action_plan()
        manager = _build_manager(container, plan)
        manager._plan_parser.parse.side_effect = InvalidPlanError("bad plan")
        _arrange_pending_action_turn(manager)
        _arrange_resumed_turn_report(manager, present=True)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            require_approval=False,
            message=REPLY,
        )

        # Assert: the fallback re-execute is unchanged (no seeded plan)...
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert execute_kwargs.get("plan") is None
        # ...and the reply is recorded on the report the replan wrote.
        written = manager._file_system_manager.find_call_by_path(
            "write_file", REPORT_PATH
        )
        content = written.args[1]
        assert "Validation Failed" in content
        assert "## User Request" in content
        assert REPLY in content
        # Assert: the augmented turn is promoted into the prune-exempt scope.
        preserve = manager._session_service.preserve_turn_in_session_context
        preserve.assert_called_once_with(Path(TURN03))
        assert result[0] == "follow-up"

    def test_unparseable_plan_skips_recording_when_report_absent(
        self, container
    ) -> None:
        # Arrange: the plan cannot be parsed and no report exists after execute
        # returned (execution aborted before finalization).
        plan = _action_plan()
        manager = _build_manager(container, plan)
        manager._plan_parser.parse.side_effect = InvalidPlanError("bad plan")
        _arrange_pending_action_turn(manager)
        _arrange_resumed_turn_report(manager, present=False)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            require_approval=False,
            message=REPLY,
        )

        # Assert: the recording step is guarded on file existence, not asserted.
        orchestrator.execute.assert_called_once()
        manager._file_system_manager.write_file.assert_not_called()
        manager._session_service.preserve_turn_in_session_context.assert_not_called()
        assert result[0] == "follow-up"

    def test_unparseable_plan_without_reply_stays_byte_identical(
        self, container
    ) -> None:
        # Arrange: the plan cannot be parsed and no reply is injected.
        plan = _action_plan()
        manager = _build_manager(container, plan)
        _arrange_pending_action_turn(manager)
        _arrange_resumed_turn_report(manager, present=True)
        orchestrator = _orchestrator_with_report()

        # Act
        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            require_approval=False,
        )

        # Assert: the bare re-execute path records nothing and promotes nothing.
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs.get("plan") is None
        manager._file_system_manager.write_file.assert_not_called()
        manager._session_service.preserve_turn_in_session_context.assert_not_called()
        assert result[0] == "follow-up"


class TestMarkedInterruptedTurnRecovery:
    """A marked non-communication turn recovers instead of replaying."""

    def test_marked_turn_without_reply_recovers_and_plans_next(self, container) -> None:
        plan = _action_plan()
        manager = _build_manager(container, plan)
        _arrange_marked_interrupted_turn(manager)
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            require_approval=False,
        )

        # The abandoned plan is never handed to execute; the successor is.
        orchestrator.execute.assert_called_once()
        executed = orchestrator.execute.call_args.kwargs["plan_path"]
        assert TURN04 in executed
        assert TURN03 not in executed
        # The killed turn is finalized with an INTERRUPTED report.
        report = manager._report_formatter.format.call_args.args[0]
        assert report.run_summary.status is RunStatus.INTERRUPTED
        assert [log.status for log in report.action_logs] == [ActionStatus.INTERRUPTED]
        assert report.user_request is None
        transition = manager._session_service.transition_to_next_turn.call_args
        assert transition.kwargs["plan_path"] == PLAN_PATH
        # The successor is planned from scratch against the observed workspace.
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN04, message=None
        )
        assert result[0] == "follow-up"

    def test_marked_turn_with_reply_records_user_request(self, container) -> None:
        plan = _action_plan()
        manager = _build_manager(container, plan)
        _arrange_marked_interrupted_turn(manager)
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            require_approval=False,
            message=REPLY,
        )

        # The reply seeds the successor; the abandoned plan is not replayed.
        orchestrator.execute.assert_called_once()
        executed = orchestrator.execute.call_args.kwargs["plan_path"]
        assert TURN04 in executed
        assert TURN03 not in executed
        manager._session_planner.trigger_new_plan.assert_called_once_with(
            TURN04, message=REPLY
        )
        # The reply is carried as the interrupted report's User Request.
        report = manager._report_formatter.format.call_args.args[0]
        assert report.run_summary.status is RunStatus.INTERRUPTED
        assert report.user_request == REPLY
        assert result[0] == "follow-up"

    def test_marked_unparseable_plan_falls_through_to_reexecute(
        self, container
    ) -> None:
        plan = _action_plan()
        manager = _build_manager(container, plan)
        manager._plan_parser.parse.side_effect = InvalidPlanError("bad plan")
        _arrange_pending_action_turn(manager)
        manager._file_system_manager.path_exists.side_effect = _marker_present
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name="follow-up",
            orchestrator=orchestrator,
            require_approval=False,
        )

        # The unparseable marked plan falls through to today's bare re-execute.
        orchestrator.execute.assert_called_once()
        assert orchestrator.execute.call_args.kwargs["plan_path"] == PLAN_PATH
        manager._report_formatter.format.assert_not_called()
        manager._session_service.transition_to_next_turn.assert_not_called()
        manager._session_planner.trigger_new_plan.assert_not_called()
        assert result[0] == "follow-up"
