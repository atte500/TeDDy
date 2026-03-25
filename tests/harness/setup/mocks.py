from unittest.mock import Mock, MagicMock, patch
import pytest
import pyperclip
from tests.harness.setup.test_environment import POSIXPathMock


@pytest.fixture
def mock_config(container):
    from teddy_executor.core.ports.outbound import IConfigService

    mock = Mock(spec=IConfigService)
    container.register(IConfigService, instance=mock)
    return mock


@pytest.fixture
def mock_user_interactor(container):
    from teddy_executor.core.ports.outbound import IUserInteractor

    mock = Mock(spec=IUserInteractor)
    container.register(IUserInteractor, instance=mock)
    return mock


@pytest.fixture
def mock_fs(container):
    from teddy_executor.core.ports.outbound import IFileSystemManager

    mock = POSIXPathMock(spec=IFileSystemManager)
    mock.get_context_paths.return_value = {}
    mock.read_files_in_vault.return_value = {}
    container.register(IFileSystemManager, instance=mock)
    return mock


@pytest.fixture
def mock_env(container):
    from teddy_executor.core.ports.outbound import ISystemEnvironment

    mock = Mock(spec=ISystemEnvironment)
    container.register(ISystemEnvironment, instance=mock)
    return mock


@pytest.fixture
def mock_shell(container):
    from teddy_executor.core.ports.outbound import IShellExecutor

    mock = Mock(spec=IShellExecutor)
    container.register(IShellExecutor, instance=mock)
    return mock


@pytest.fixture
def mock_scraper(container):
    from teddy_executor.core.ports.outbound import IWebScraper

    mock = Mock(spec=IWebScraper)
    container.register(IWebScraper, instance=mock)
    return mock


@pytest.fixture
def mock_searcher(container):
    from teddy_executor.core.ports.outbound import IWebSearcher

    mock = Mock(spec=IWebSearcher)
    container.register(IWebSearcher, instance=mock)
    return mock


@pytest.fixture
def mock_session_manager(container):
    from teddy_executor.core.ports.outbound import ISessionManager

    mock = Mock(spec=ISessionManager)
    container.register(ISessionManager, instance=mock)
    return mock


@pytest.fixture
def mock_planning_service(container):
    from teddy_executor.core.ports.inbound.planning_use_case import (
        IPlanningUseCase,
    )

    mock = Mock(spec=IPlanningUseCase)
    container.register(IPlanningUseCase, instance=mock)
    return mock


@pytest.fixture
def mock_tree_gen(container):
    from teddy_executor.core.ports.outbound import IRepoTreeGenerator

    mock = Mock(spec=IRepoTreeGenerator)
    mock.generate_tree.return_value = ""
    container.register(IRepoTreeGenerator, instance=mock)
    return mock


@pytest.fixture
def mock_action_factory(container):
    from teddy_executor.core.services.action_factory import IActionFactory

    mock = Mock(spec=IActionFactory)
    container.register(IActionFactory, instance=mock)
    return mock


@pytest.fixture
def mock_plan_parser(container):
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser

    mock = Mock(spec=IPlanParser)
    container.register(IPlanParser, instance=mock)
    return mock


@pytest.fixture
def mock_plan_validator(container):
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator

    mock = Mock(spec=IPlanValidator)
    container.register(IPlanValidator, instance=mock)
    return mock


@pytest.fixture(autouse=True)
def mock_plan_reviewer(container):
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

    mock = Mock(spec=IPlanReviewer)
    # Default pass-through behavior for review methods
    mock.review.side_effect = lambda p: p
    mock.review_action.return_value = True  # Default to auto-approving in tests

    container.register(IPlanReviewer, instance=mock)
    return mock


@pytest.fixture
def mock_action_dispatcher(container):
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher

    mock = Mock(spec=ActionDispatcher)
    container.register(ActionDispatcher, instance=mock)
    return mock


@pytest.fixture
def mock_run_plan(container):
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )

    mock = Mock(spec=IRunPlanUseCase)
    # The CLI resolves concrete ExecutionOrchestrator directly
    container.register(IRunPlanUseCase, instance=mock)
    container.register(ExecutionOrchestrator, instance=mock)
    return mock


@pytest.fixture
def mock_context_service(container):
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.services.context_service import ContextService

    mock = Mock(spec=IGetContextUseCase)
    container.register(IGetContextUseCase, instance=mock)
    # The CLI resolves concrete ContextService directly in some places
    container.register(ContextService, instance=mock)
    return mock


@pytest.fixture
def mock_edit_simulator(container):
    from teddy_executor.core.services.edit_simulator import EditSimulator

    mock = Mock(spec=EditSimulator)
    container.register(EditSimulator, instance=mock)
    return mock


@pytest.fixture
def mock_inspector(container):
    from teddy_executor.core.ports.outbound import IEnvironmentInspector

    mock = Mock(spec=IEnvironmentInspector)
    mock.get_git_status.return_value = None
    container.register(IEnvironmentInspector, instance=mock)
    return mock


@pytest.fixture
def mock_report_formatter(container):
    from teddy_executor.core.ports.outbound import IMarkdownReportFormatter

    mock = Mock(spec=IMarkdownReportFormatter)
    container.register(IMarkdownReportFormatter, instance=mock)
    return mock


@pytest.fixture
def mock_llm_client(container):
    from teddy_executor.core.ports.outbound import ILlmClient

    mock = Mock(spec=ILlmClient)

    # Create a structured ModelResponse mock
    mock_response = MagicMock()
    mock_choice = MagicMock()

    # CRITICAL: Ensure the mock content is a real string to prevent
    # Pathlib TypeError in integration tests that write the plan to disk.
    mock_choice.message.content = "# Mock Plan\nRationale: Test\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"

    mock.get_completion.return_value = mock_response
    mock.get_token_count.return_value = 100
    mock.get_completion_cost.return_value = 0.01

    container.register(ILlmClient, instance=mock)
    return mock


@pytest.fixture(autouse=True)
def mock_pyperclip():
    """
    Automatically mock pyperclip for all tests to prevent clipboard pollution.
    Raises PyperclipException to force the application to skip clipboard logging.
    """
    with patch(
        "pyperclip.copy",
        side_effect=pyperclip.PyperclipException("Clipboard not available in test"),
    ) as mock_copy:
        yield mock_copy
