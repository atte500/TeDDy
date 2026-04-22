from unittest.mock import MagicMock, patch
import pytest
import pyperclip
from tests.harness.setup.mocking import UnifiedMock, register_mock


@pytest.fixture
def mock_config(container):
    from teddy_executor.core.ports.outbound import IConfigService

    return register_mock(container, IConfigService)


@pytest.fixture
def mock_user_interactor(container):
    from teddy_executor.core.ports.outbound import IUserInteractor

    return register_mock(container, IUserInteractor)


@pytest.fixture
def mock_fs(container):
    from teddy_executor.core.ports.outbound import IFileSystemManager

    mock = register_mock(container, IFileSystemManager)
    mock.get_context_paths.return_value = {}
    mock.read_files_in_vault.return_value = {}
    return mock


@pytest.fixture
def mock_env(container):
    from teddy_executor.core.ports.outbound import ISystemEnvironment

    return register_mock(container, ISystemEnvironment)


@pytest.fixture
def mock_shell(container):
    from teddy_executor.core.ports.outbound import IShellExecutor

    return register_mock(container, IShellExecutor)


@pytest.fixture
def mock_scraper(container):
    from teddy_executor.core.ports.outbound import IWebScraper

    mock = UnifiedMock(spec=IWebScraper)
    container.register(IWebScraper, instance=mock)
    return mock


@pytest.fixture
def mock_searcher(container):
    from teddy_executor.core.ports.outbound import IWebSearcher

    mock = UnifiedMock(spec=IWebSearcher)
    container.register(IWebSearcher, instance=mock)
    return mock


@pytest.fixture
def mock_session_manager(container):
    from teddy_executor.core.ports.outbound import ISessionManager

    mock = UnifiedMock(spec=ISessionManager)
    container.register(ISessionManager, instance=mock)
    return mock


@pytest.fixture
def mock_planning_service(container):
    from teddy_executor.core.ports.inbound.planning_use_case import (
        IPlanningUseCase,
    )

    mock = UnifiedMock(spec=IPlanningUseCase)
    container.register(IPlanningUseCase, instance=mock)
    return mock


@pytest.fixture
def mock_tree_gen(container):
    from teddy_executor.core.ports.outbound import IRepoTreeGenerator

    mock = UnifiedMock(spec=IRepoTreeGenerator)
    mock.generate_tree.return_value = ""
    container.register(IRepoTreeGenerator, instance=mock)
    return mock


@pytest.fixture
def mock_action_factory(container):
    from teddy_executor.core.services.action_factory import IActionFactory

    mock = UnifiedMock(spec=IActionFactory)
    container.register(IActionFactory, instance=mock)
    return mock


@pytest.fixture
def mock_plan_parser(container):
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser

    mock = UnifiedMock(spec=IPlanParser)
    container.register(IPlanParser, instance=mock)
    return mock


@pytest.fixture
def mock_plan_validator(container):
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator

    mock = UnifiedMock(spec=IPlanValidator)
    container.register(IPlanValidator, instance=mock)
    return mock


@pytest.fixture(autouse=True)
def mock_plan_reviewer(container):
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

    mock = UnifiedMock(spec=IPlanReviewer)
    # Default pass-through behavior for review methods
    mock.review.side_effect = lambda p: p
    # Default to auto-approving in tests with an empty captured message
    mock.review_action.return_value = (True, "")

    container.register(IPlanReviewer, instance=mock)
    return mock


@pytest.fixture
def mock_action_dispatcher(container):
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher

    mock = UnifiedMock(spec=ActionDispatcher)
    container.register(ActionDispatcher, instance=mock)
    return mock


@pytest.fixture
def mock_run_plan(container):
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )

    mock = UnifiedMock(spec=IRunPlanUseCase)
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

    mock = UnifiedMock(spec=IGetContextUseCase)
    container.register(IGetContextUseCase, instance=mock)
    # The CLI resolves concrete ContextService directly in some places
    container.register(ContextService, instance=mock)
    return mock


@pytest.fixture
def mock_prompt_manager(container):
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

    mock = UnifiedMock(spec=IPromptManager)
    # Default for unpacking
    mock.resolve_agent_metadata.return_value = ("pathfinder", {}, "meta.yaml")
    # Default for strings
    mock.resolve_message.return_value = "default message"
    mock.async_resolve_message.return_value = "default message"
    mock.async_fetch_system_prompt.return_value = "system prompt"
    mock.async_log_telemetry.return_value = 0.01

    container.register(IPromptManager, instance=mock)
    return mock


@pytest.fixture
def mock_edit_simulator(container):
    from teddy_executor.core.services.edit_simulator import EditSimulator

    mock = UnifiedMock(spec=EditSimulator)
    container.register(EditSimulator, instance=mock)
    return mock


@pytest.fixture
def mock_inspector(container):
    from teddy_executor.core.ports.outbound import IEnvironmentInspector

    mock = UnifiedMock(spec=IEnvironmentInspector)
    mock.get_git_status.return_value = None
    container.register(IEnvironmentInspector, instance=mock)
    return mock


@pytest.fixture
def mock_report_formatter(container):
    from teddy_executor.core.ports.outbound import IMarkdownReportFormatter

    mock = UnifiedMock(spec=IMarkdownReportFormatter)
    container.register(IMarkdownReportFormatter, instance=mock)
    return mock


@pytest.fixture
def mock_llm_client(container):
    from teddy_executor.core.ports.outbound import ILlmClient

    mock = UnifiedMock(spec=ILlmClient)

    # Create a structured ModelResponse mock
    mock_response = UnifiedMock()
    mock_choice = MagicMock()

    # CRITICAL: Ensure the mock content is a real string to prevent
    # Pathlib TypeError in integration tests that write the plan to disk.
    mock_choice.message.content = "# Mock Plan\nRationale: Test\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"

    mock.get_completion.return_value = mock_response
    # Ensure the async version also returns the structured response
    mock.async_get_completion.return_value = mock_response

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
