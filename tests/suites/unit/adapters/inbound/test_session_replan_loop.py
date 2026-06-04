from punq import Container
from datetime import datetime, timezone
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from unittest.mock import Mock, create_autospec
from teddy_executor.adapters.inbound.cli_helpers import handle_report_output
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.adapters.inbound.session_cli_handlers import (
    handle_new_session,
    handle_resume_session,
)


class MockFormatter(IMarkdownReportFormatter):
    def format(self, report):
        return "Mock Report"


def test_handle_new_session_loops_multiple_turns_when_non_interactive():
    # Arrange
    container = Container()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_user_interactor = Mock(spec=IUserInteractor)
    mock_orchestrator = Mock(spec=IRunPlanUseCase)
    mock_llm_client = Mock(spec=ILlmClient)
    mock_config_service = Mock(spec=IConfigService)
    mock_loop_guard = create_autospec(ISessionLoopGuard)
    mock_prompt_manager = Mock(spec=IPromptManager)

    container.register(IInitUseCase, instance=Mock(spec=IInitUseCase))
    container.register(IPromptManager, instance=mock_prompt_manager)
    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IUserInteractor, instance=mock_user_interactor)
    container.register(IRunPlanUseCase, instance=mock_orchestrator)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)
    container.register(ISessionLoopGuard, instance=mock_loop_guard)
    container.register(IMarkdownReportFormatter, MockFormatter)

    mock_llm_client.validate_config.return_value = []
    mock_user_interactor.ask_question.return_value = "Do multiple turns"
    mock_session_manager.create_session.return_value = ".teddy/sessions/multi-turn"

    fake_report = Mock(spec=ExecutionReport)
    fake_report.run_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )
    fake_report.metadata = {}
    mock_orchestrator.resume.return_value = fake_report

    # Loop guard allows 2 turns:
    # turn_count=1: should_continue(1) -> True
    # turn_count=2: should_continue(2) -> False
    # turn_count=1: should_continue(1, cost, interact) -> True
    # turn_count=2: should_continue(2, cost, interact) -> False
    mock_loop_guard.should_continue.side_effect = lambda tc, cost, interact: tc < 2

    # Act
    handle_new_session(
        container=container,
        name=None,
        agent="pathfinder",
        interactive=False,
        no_copy=True,
        message="Do multiple turns",
    )

    # Assert
    assert mock_orchestrator.resume.call_count == 2


def test_handle_resume_session_loops_multiple_turns_when_non_interactive():
    # Arrange
    container = Container()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_orchestrator = Mock(spec=IRunPlanUseCase)
    mock_llm_client = Mock(spec=ILlmClient)
    mock_config_service = Mock(spec=IConfigService)
    mock_loop_guard = create_autospec(ISessionLoopGuard)
    mock_prompt_manager = Mock(spec=IPromptManager)

    container.register(IInitUseCase, instance=Mock(spec=IInitUseCase))
    container.register(IPromptManager, instance=mock_prompt_manager)
    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IRunPlanUseCase, instance=mock_orchestrator)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)
    container.register(ISessionLoopGuard, instance=mock_loop_guard)
    container.register(IMarkdownReportFormatter, MockFormatter)
    mock_session_repo = Mock(spec=ISessionRepository)
    mock_session_repo.load_meta.return_value = {}
    container.register(
        ISessionRepository,
        instance=mock_session_repo,
    )
    mock_config_service.get_setting.return_value = "unknown"

    mock_llm_client.validate_config.return_value = []
    mock_session_manager.resolve_session_from_path.return_value = "my-session"

    fake_report = Mock(spec=ExecutionReport)
    fake_report.run_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )
    fake_report.metadata = {}
    mock_orchestrator.resume.return_value = fake_report

    # turn_count=1: should_continue(1, cost, interact) -> True
    # turn_count=2: should_continue(2, cost, interact) -> False
    mock_loop_guard.should_continue.side_effect = lambda tc, cost, interact: tc < 2

    # Act
    handle_resume_session(
        container=container,
        path="my-session",
        interactive=False,
        no_copy=True,
    )

    # Assert
    assert mock_orchestrator.resume.call_count == 2


def test_handle_report_output_does_not_exit_in_session_mode():
    """
    VERIFIES FIX: Validation failures in session mode should not trigger typer.Exit,
    as they are handled by an automated re-plan loop.
    """
    container = Container()
    container.register(IMarkdownReportFormatter, MockFormatter)
    container.register(IUserInteractor, Mock(spec=IUserInteractor))

    report = ExecutionReport(
        plan_title="Failing Plan",
        run_summary=RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
    )

    # With the fix, we can now pass exit_on_failure=False.
    # This should return normally instead of raising click.exceptions.Exit.
    handle_report_output(
        container, report, no_copy=True, silent=True, exit_on_failure=False
    )
