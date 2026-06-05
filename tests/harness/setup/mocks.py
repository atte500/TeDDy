from typing import Any
import pytest
import pyperclip
from tests.harness.setup.mocking import POSIXPathMock, register_mock


@pytest.fixture
def mock_config(container):
    from teddy_executor.core.ports.outbound import IConfigService

    return register_mock(container, IConfigService)


@pytest.fixture
def mock_user_interactor(container):
    from teddy_executor.core.ports.outbound import IUserInteractor

    return register_mock(container, IUserInteractor)


@pytest.fixture
def mock_fs(container) -> Any:
    from teddy_executor.core.ports.outbound import IFileSystemManager

    mock = register_mock(container, IFileSystemManager)
    mock.get_context_paths.return_value = {}
    mock.read_files_in_vault.return_value = {}
    mock.is_dir.return_value = False
    mock.list_directory_recursive.return_value = []
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

    return register_mock(container, IWebScraper)


@pytest.fixture
def mock_searcher(container):
    from teddy_executor.core.ports.outbound import IWebSearcher

    return register_mock(container, IWebSearcher)


@pytest.fixture
def mock_session_manager(container):
    from teddy_executor.core.ports.outbound import ISessionManager

    return register_mock(container, ISessionManager)


@pytest.fixture
def mock_session_loop_guard(container):
    from teddy_executor.core.ports.outbound.session_loop_guard import (
        ISessionLoopGuard,
    )

    return register_mock(container, ISessionLoopGuard)


@pytest.fixture
def mock_planning_service(container):
    from teddy_executor.core.ports.inbound.planning_use_case import (
        IPlanningUseCase,
    )

    return register_mock(container, IPlanningUseCase)


@pytest.fixture
def mock_tree_gen(container):
    from teddy_executor.core.ports.outbound import IRepoTreeGenerator

    mock = register_mock(container, IRepoTreeGenerator)
    mock.generate_tree.return_value = ""
    return mock


@pytest.fixture
def mock_action_factory(container):
    from teddy_executor.core.services.action_factory import IActionFactory

    return register_mock(container, IActionFactory)


@pytest.fixture
def mock_plan_parser(container):
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser

    return register_mock(container, IPlanParser)


@pytest.fixture
def mock_plan_validator(container):
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator

    return register_mock(container, IPlanValidator)


@pytest.fixture
def mock_plan_reviewer(container):
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

    mock = register_mock(container, IPlanReviewer)
    # Default pass-through behavior for review methods
    mock.review.side_effect = lambda p, **kwargs: p
    # Default to auto-approving in tests with an empty captured message
    mock.review_action.return_value = (True, "")

    return mock


@pytest.fixture
def mock_action_dispatcher(container):
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher

    return register_mock(container, ActionDispatcher)


@pytest.fixture
def mock_run_plan(container):
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )

    mock = register_mock(container, IRunPlanUseCase)
    # The CLI resolves concrete ExecutionOrchestrator directly
    container.register(ExecutionOrchestrator, instance=mock)
    return mock


@pytest.fixture
def mock_context_service(container):
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.services.context_service import ContextService

    mock = register_mock(container, IGetContextUseCase)
    # The CLI resolves concrete ContextService directly in some places
    container.register(ContextService, instance=mock)
    return mock


@pytest.fixture
def mock_prompt_manager(container):
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

    mock = register_mock(container, IPromptManager)
    # Default for unpacking
    mock.resolve_agent_metadata.return_value = ("pathfinder", {}, "meta.yaml")
    # Default for strings
    mock.resolve_message.return_value = "default message"

    return mock


@pytest.fixture
def mock_edit_simulator(container):
    from teddy_executor.core.services.edit_simulator import EditSimulator

    return register_mock(container, EditSimulator)


@pytest.fixture
def mock_inspector(container):
    from teddy_executor.core.ports.outbound import IEnvironmentInspector

    mock = register_mock(container, IEnvironmentInspector)
    mock.get_git_status.return_value = None
    return mock


@pytest.fixture
def mock_report_formatter(container):
    from teddy_executor.core.ports.outbound import IMarkdownReportFormatter

    return register_mock(container, IMarkdownReportFormatter)


@pytest.fixture
def mock_time_service(container):
    from teddy_executor.core.ports.outbound.time_service import ITimeService

    mock = register_mock(container, ITimeService)
    mock.sleep_calls = []
    original_sleep = mock.sleep

    def _track_sleep(duration: float) -> None:
        mock.sleep_calls.append(duration)
        original_sleep(duration)

    mock.sleep.side_effect = _track_sleep
    return mock


@pytest.fixture
def mock_llm_client(container):
    from teddy_executor.core.ports.outbound import ILlmClient

    mock = register_mock(container, ILlmClient)

    # Create a structured ModelResponse mock
    mock_response = POSIXPathMock()
    mock_choice = POSIXPathMock()

    # CRITICAL: Ensure the mock content is a real string to prevent
    # Pathlib TypeError in integration tests that write the plan to disk.
    mock_choice.message.content = "# Mock Plan\nRationale: Test\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"

    mock.get_completion.return_value = mock_response

    mock.get_token_count.return_value = 100
    mock.get_completion_cost.return_value = 0.01
    mock.get_context_window.return_value = 128000

    return mock


@pytest.fixture(autouse=True)
def mock_pyperclip(monkeypatch):
    """
    Automatically mock pyperclip for all tests to prevent clipboard pollution.
    Raises PyperclipException to force the application to skip clipboard logging.
    """
    mock_copy = POSIXPathMock()
    mock_copy.side_effect = pyperclip.PyperclipException(
        "Clipboard not available in test"
    )
    monkeypatch.setattr("pyperclip.copy", mock_copy)
    yield mock_copy
