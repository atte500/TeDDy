"""Unit tests: a present-but-blank `-m` on a non-awaiting PENDING_PLAN resume.

A blank ``teddy resume -m ""`` on a pending plan must ask the human for the
next instruction when one is reachable, seed the reply into
``plan.metadata["user_request"]``, and run the pending plan as its first
execution. Without a terminal the branch keeps the bare
``execute(plan_path=...)`` path; an empty reply terminates; an absent ``-m``
never prompts. A flagged awaiting turn keeps its own prompt because the
awaiting-reply short-circuit runs first.
"""

from datetime import datetime, timezone
from unittest.mock import create_autospec

import pytest

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
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
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

SESSION = "feature"
TURN05 = ".teddy/sessions/feature/05"
PLAN_PATH = f"{TURN05}/plan.md"
PROMPT = "What would you like to do next?"
AWAIT_PROMPT = "The agent is awaiting your reply. How do you want to proceed?"


def _action_plan() -> Plan:
    return Plan(
        title="Run something",
        rationale="Pending action turn",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo hi"},
                description="run",
            )
        ],
    )


@pytest.fixture
def manager(container):
    """SessionLifecycleManager with auto-specced port doubles.

    ``isatty()`` is pinned False by default; a test that models a human at the
    terminal flips it through ``manager._system_environment.isatty``.
    """
    system_environment = register_mock(container, ISystemEnvironment)
    system_environment.isatty.return_value = False
    time_service = register_mock(container, ITimeService)
    time_service.now_utc.return_value = datetime(2026, 11, 6, tzinfo=timezone.utc)
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
        system_environment=system_environment,
        plan_parser=register_mock(container, IPlanParser),
        time_service=time_service,
        report_assembler=ExecutionReportAssembler(),
    )
    return SessionLifecycleManager(ports=ports)


def _orchestrator_with_report():
    orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    orchestrator.execute.return_value = create_autospec(ExecutionReport, instance=True)
    return orchestrator


def _arrange_pending_plan(manager, plan) -> None:
    manager._session_service.get_session_state.return_value = (
        SessionState.PENDING_PLAN,
        TURN05,
    )
    manager._session_service.load_turn_meta.return_value = {}
    manager._file_system_manager.read_raw_file.return_value = "# plan"
    manager._plan_parser.parse.return_value = plan
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{turn_dir}/{filename}"
    )


class TestBlankMessageAtTerminal:
    """Present-but-blank `-m` with a human reachable."""

    def test_prompts_and_seeds_the_pending_plan(self, manager):
        plan = _action_plan()
        _arrange_pending_plan(manager, plan)
        manager._system_environment.isatty.return_value = True
        manager._user_interactor.ask_question.return_value = "refactor auth"
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name=SESSION,
            orchestrator=orchestrator,
            require_approval=True,
            message="",
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        manager._plan_parser.parse.assert_called_once()
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs["plan"] is plan
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert plan.metadata["user_request"] == "refactor auth"
        assert result[0] == SESSION

    def test_prompts_and_seeds_under_yolo_too(self, manager):
        plan = _action_plan()
        _arrange_pending_plan(manager, plan)
        manager._system_environment.isatty.return_value = True
        manager._user_interactor.ask_question.return_value = "next task"
        orchestrator = _orchestrator_with_report()

        manager.resume(
            session_name=SESSION,
            orchestrator=orchestrator,
            require_approval=False,
            message="",
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert execute_kwargs["plan"] is plan
        assert plan.metadata["user_request"] == "next task"

    def test_empty_reply_terminates_without_execution(self, manager):
        _arrange_pending_plan(manager, _action_plan())
        manager._system_environment.isatty.return_value = True
        manager._user_interactor.ask_question.return_value = ""
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name=SESSION,
            orchestrator=orchestrator,
            require_approval=True,
            message="",
        )

        manager._user_interactor.ask_question.assert_called_once_with(PROMPT)
        orchestrator.execute.assert_not_called()
        assert result == (SESSION, None)


class TestBlankMessageWithoutTerminal:
    """Present-but-blank `-m` with nobody to ask keeps the bare path."""

    def test_does_not_prompt_and_keeps_the_bare_path(self, manager):
        _arrange_pending_plan(manager, _action_plan())
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name=SESSION,
            orchestrator=orchestrator,
            require_approval=True,
            message="",
        )

        manager._user_interactor.ask_question.assert_not_called()
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert "plan" not in execute_kwargs
        assert execute_kwargs["plan_path"] == PLAN_PATH
        assert result[0] == SESSION


class TestAbsentMessage:
    """An omitted `-m` never prompts and runs the pending plan."""

    def test_never_prompts_even_with_a_terminal(self, manager):
        _arrange_pending_plan(manager, _action_plan())
        manager._system_environment.isatty.return_value = True
        orchestrator = _orchestrator_with_report()

        manager.resume(
            session_name=SESSION,
            orchestrator=orchestrator,
            require_approval=True,
            message=None,
        )

        manager._user_interactor.ask_question.assert_not_called()
        execute_kwargs = orchestrator.execute.call_args.kwargs
        assert "plan" not in execute_kwargs
        assert execute_kwargs["plan_path"] == PLAN_PATH


class TestAwaitingTurnOrdering:
    """A flagged awaiting turn keeps its own prompt; no next-instruction ask."""

    def test_flagged_turn_prompts_for_the_reply_only(self, manager):
        manager._session_service.get_session_state.return_value = (
            SessionState.PENDING_PLAN,
            TURN05,
        )
        manager._session_service.load_turn_meta.return_value = {"awaiting_reply": True}
        manager._system_environment.isatty.return_value = True
        manager._user_interactor.ask_question.return_value = ""
        orchestrator = _orchestrator_with_report()

        result = manager.resume(
            session_name=SESSION,
            orchestrator=orchestrator,
            require_approval=True,
            message="",
        )

        manager._user_interactor.ask_question.assert_called_once_with(AWAIT_PROMPT)
        orchestrator.execute.assert_not_called()
        assert result == (SESSION, None)
