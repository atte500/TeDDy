from datetime import datetime, timezone
from unittest.mock import MagicMock, ANY
import pytest
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    container,
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_plan_validator,
    mock_plan_parser,
    mock_user_interactor,
):
    from unittest.mock import MagicMock
    from teddy_executor.core.services.session_lifecycle_manager import (
        SessionLifecycleManager,
    )

    # Manually instantiate sub-services using the container to resolve ports
    replanner = SessionReplanner(
        file_system_manager=container.resolve(IFileSystemManager),
        planning_service=container.resolve(IPlanningUseCase),
    )

    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

    # Instantiate the orchestrator with its dependencies
    mock_prompt_manager = MagicMock(spec=IPromptManager)
    mock_prompt_manager.fetch_system_prompt.return_value = "mock prompt content"
    mock_llm_client = MagicMock(spec=ILlmClient)
    mock_llm_client.get_text_token_count.return_value = 100

    orchestrator_instance = SessionOrchestrator(
        execution_orchestrator=container.resolve(IRunPlanUseCase),
        session_service=container.resolve(ISessionManager),
        file_system_manager=container.resolve(IFileSystemManager),
        plan_validator=container.resolve(IPlanValidator),
        plan_parser=container.resolve(IPlanParser),
        user_interactor=container.resolve(IUserInteractor),
        lifecycle_manager=MagicMock(spec=SessionLifecycleManager),
        replanner=replanner,
        context_service=container.resolve(IGetContextUseCase),
        config_service=container.resolve(IConfigService),
        llm_client=mock_llm_client,
        prompt_manager=mock_prompt_manager,
    )

    # Register as instances to bypass punq auto-wiring for untyped constructors
    container.register(SessionReplanner, instance=replanner)
    container.register(SessionOrchestrator, instance=orchestrator_instance)

    return orchestrator_instance


def test_session_orchestrator_triggers_transition_on_success(  # noqa: PLR0913
    orchestrator,
    mock_run_plan,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
):
    """
    SessionOrchestrator should call SessionLifecycleManager.finalize_turn
    after successful plan execution.
    """
    # Arrange
    # Mock successful execution
    mock_run_plan.execute.return_value = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        plan_title="Test Plan",
        rationale="Test Rationale",
    )

    plan_content = MarkdownPlanBuilder("Test").build()
    plan_path = "path/to/01/plan.md"

    mock_fs.path_exists.return_value = True

    # Mock parsing and validation to allow execution flow
    mock_plan_parser.parse.return_value = MagicMock()
    mock_plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

    # Assert
    # Verify execution was called
    mock_run_plan.execute.assert_called_once()

    # Verify delegation to lifecycle manager
    orchestrator._lifecycle_manager.finalize_turn.assert_called_once_with(
        plan_path, mock_run_plan.execute.return_value, plan=ANY
    )
