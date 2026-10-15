"""Unit tests: session termination notice rendering (Slice 00-37, Logic).

Both termination notices emitted by ``SessionOrchestrator.execute`` -- the
empty-message termination and the aborted-session termination -- must render as
ONE yellow stderr line ending with the shared ``RESUME_HINT``, replacing the
previous two-line RED form that carried the retired ``[session_path]`` hint.
"""

import types
from datetime import datetime, timezone
from unittest.mock import Mock

import typer

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    ExecutionReport,
    Plan,
    ProjectContext,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.utils import session_notices

EMPTY_MESSAGE_NOTICE = (
    "Session terminated (empty message). To continue the session, use `teddy resume`."
)
ABORTED_NOTICE = "Session terminated. To continue the session, use `teddy resume`."


def _capture_secho(monkeypatch) -> list[tuple[str, dict]]:
    """Record every ``typer.secho`` call the orchestrator makes."""
    calls: list[tuple[str, dict]] = []

    def _fake_secho(text="", **kwargs):
        calls.append((text, kwargs))

    monkeypatch.setattr(
        "teddy_executor.core.services.session_orchestrator.typer.secho",
        _fake_secho,
    )
    return calls


def _build_orchestrator(*, parser, validator, exec_orch, fs, interactor):
    context_service = Mock(spec=IGetContextUseCase)
    context_service.get_context.return_value = ProjectContext(
        header="", content="", items=[]
    )
    return SessionOrchestrator(
        execution_orchestrator=exec_orch,
        session_service=Mock(spec=ISessionManager),
        file_system_manager=fs,
        plan_validator=validator,
        plan_parser=parser,
        user_interactor=interactor,
        lifecycle_manager=Mock(spec=SessionLifecycleManager),
        replanner=Mock(spec=SessionReplanner),
        context_service=context_service,
        config_service=Mock(spec=IConfigService),
        llm_client=Mock(spec=ILlmClient),
        prompt_manager=Mock(spec=IPromptManager),
        pruning_service=None,
    )


def _notice_calls(calls: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return [call for call in calls if "Session terminated" in call[0]]


def test_format_termination_notice_appends_the_shared_resume_hint():
    """The composition helper appends the shared hint to the situation lead-in."""
    assert session_notices.format_termination_notice("Session terminated.") == (
        ABORTED_NOTICE
    )


def test_empty_message_termination_notice_is_one_yellow_stderr_line(monkeypatch):
    """Empty-message termination: ONE yellow stderr line ending with the hint."""
    # Arrange
    calls = _capture_secho(monkeypatch)

    fs = Mock(spec=IFileSystemManager)
    fs.path_exists.return_value = True
    validator = Mock(spec=IPlanValidator)
    validator.validate.return_value = []
    parser = Mock(spec=IPlanParser)

    plan = Plan(
        title="Test Communication Turn",
        rationale="test",
        actions=[Mock(spec=ActionData, type="MESSAGE", params={}, description="Test")],
        metadata={"Agent": "test"},
        is_session=True,
    )
    plan.is_communication_turn = types.MethodType(lambda self: True, plan)
    parser.parse.return_value = plan

    exec_orch = Mock(spec=IRunPlanUseCase)
    now = datetime.now(timezone.utc)
    exec_orch.execute.return_value = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        plan_title="Test",
        rationale="test",
        user_request=None,
        metadata={},
        is_session=True,
        original_actions=[],
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="MESSAGE",
                params={},
                details="",
            )
        ],
    )

    orchestrator = _build_orchestrator(
        parser=parser,
        validator=validator,
        exec_orch=exec_orch,
        fs=fs,
        interactor=Mock(spec=IUserInteractor),
    )

    # Act
    orchestrator.execute(
        plan_path=".teddy/sessions/test/01/plan.md",
        interactive=False,
    )

    # Assert
    notices = _notice_calls(calls)
    assert len(notices) == 1
    text, kwargs = notices[0]
    assert text == EMPTY_MESSAGE_NOTICE
    assert kwargs.get("fg") == typer.colors.YELLOW
    assert kwargs.get("err") is True


def test_aborted_termination_notice_is_one_yellow_stderr_line(monkeypatch):
    """Aborted termination: ONE yellow stderr line ending with the hint."""
    # Arrange
    calls = _capture_secho(monkeypatch)

    fs = Mock(spec=IFileSystemManager)
    fs.path_exists.return_value = True
    fs.read_file.return_value = "### Plan\nRationale"
    validator = Mock(spec=IPlanValidator)
    validator.validate.return_value = []
    parser = Mock(spec=IPlanParser)
    plan = Mock(spec=Plan)
    plan.metadata = {}
    plan.is_communication_turn.return_value = False
    parser.parse.return_value = plan

    exec_orch = Mock(spec=IRunPlanUseCase)
    now = datetime.now(timezone.utc)
    exec_orch.execute.return_value = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.ABORTED, start_time=now, end_time=now),
        user_request="Original",
        metadata={},
        action_logs=[],
        original_actions=[],
    )

    interactor = Mock(spec=IUserInteractor)
    interactor.ask_question.return_value = ""

    orchestrator = _build_orchestrator(
        parser=parser,
        validator=validator,
        exec_orch=exec_orch,
        fs=fs,
        interactor=interactor,
    )

    # Act
    orchestrator.execute(plan_path="session/turn1/plan.md", message="Start")

    # Assert
    notices = _notice_calls(calls)
    assert len(notices) == 1
    text, kwargs = notices[0]
    assert text == ABORTED_NOTICE
    assert kwargs.get("fg") == typer.colors.YELLOW
    assert kwargs.get("err") is True
