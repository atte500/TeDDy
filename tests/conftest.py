import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
import pytest

# Globally mock litellm to prevent the expensive 1.2s import in all tests.
# This ensures that even if LiteLLMAdapter is instantiated, it doesn't
# trigger the real library import.
mock_litellm = MagicMock()

# Configure a "Safe-by-Default" response for litellm.completion()
# to prevent TypeErrors when tests write plan content to disk.
_default_completion_mock = MagicMock()
_default_choice = MagicMock()
_default_choice.message.content = "# Mock Plan\nRationale: Test\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
_default_completion_mock.choices = [_default_choice]
_default_completion_mock.model = "mock-model"

mock_litellm.completion.return_value = _default_completion_mock
mock_litellm.token_counter.return_value = 100
mock_litellm.completion_cost.return_value = 0.01

sys.modules["litellm"] = mock_litellm

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase  # noqa: E402
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser  # noqa: E402
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase  # noqa: E402
from teddy_executor.core.services.context_service import ContextService  # noqa: E402
from teddy_executor.core.ports.outbound import (  # noqa: E402
    IUserInteractor,
    IFileSystemManager,
    ISystemEnvironment,
    IShellExecutor,
    IWebScraper,
    IWebSearcher,
    IRepoTreeGenerator,
    IEnvironmentInspector,
    IMarkdownReportFormatter,
    ILlmClient,
)
from teddy_executor.core.services.edit_simulator import EditSimulator  # noqa: E402
from teddy_executor.core.services.action_dispatcher import (  # noqa: E402
    ActionDispatcher,
    IActionFactory,
)
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator  # noqa: E402

# Add the project root directory to the Python path.
# This is necessary to ensure that `pytest` can correctly resolve imports
# when running tests from a specific file path, as it might not add the
# project root to `sys.path` by default in that scenario.
# We add it to the beginning of the list to ensure it's checked first.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


import teddy_executor.__main__  # noqa: E402
from teddy_executor.container import create_container  # noqa: E402

# Pre-create a base container once to avoid the overhead of
# hundreds of registrations during every test.
_BASE_CONTAINER = create_container()


@pytest.fixture
def container(monkeypatch):
    """
    Provides a fresh DI container for each test and automatically
    patches the global container in teddy_executor.__main__.
    """
    # We use a child container (or similar) if the DI library supports it,
    # but for punq, we'll just create a fresh one.
    # To optimize, we've moved the imports outside the fixture.
    c = create_container()
    monkeypatch.setattr(teddy_executor.__main__, "container", c)
    return c


@pytest.fixture
def mock_user_interactor(container):
    mock = Mock(spec=IUserInteractor)
    container.register(IUserInteractor, instance=mock)
    return mock


@pytest.fixture
def mock_fs(container):
    mock = Mock(spec=IFileSystemManager)
    container.register(IFileSystemManager, instance=mock)
    return mock


@pytest.fixture
def mock_env(container):
    mock = Mock(spec=ISystemEnvironment)
    container.register(ISystemEnvironment, instance=mock)
    return mock


@pytest.fixture
def mock_shell(container):
    mock = Mock(spec=IShellExecutor)
    container.register(IShellExecutor, instance=mock)
    return mock


@pytest.fixture
def mock_scraper(container):
    mock = Mock(spec=IWebScraper)
    container.register(IWebScraper, instance=mock)
    return mock


@pytest.fixture
def mock_searcher(container):
    mock = Mock(spec=IWebSearcher)
    container.register(IWebSearcher, instance=mock)
    return mock


@pytest.fixture
def mock_tree_gen(container):
    mock = Mock(spec=IRepoTreeGenerator)
    container.register(IRepoTreeGenerator, instance=mock)
    return mock


@pytest.fixture
def mock_action_factory(container):
    mock = Mock(spec=IActionFactory)
    container.register(IActionFactory, instance=mock)
    return mock


@pytest.fixture
def mock_plan_parser(container):
    mock = Mock(spec=IPlanParser)
    container.register(IPlanParser, instance=mock)
    return mock


@pytest.fixture
def mock_action_dispatcher(container):
    mock = Mock(spec=ActionDispatcher)
    container.register(ActionDispatcher, instance=mock)
    return mock


@pytest.fixture
def mock_run_plan(container):
    mock = Mock(spec=IRunPlanUseCase)
    container.register(IRunPlanUseCase, instance=mock)
    # The CLI resolves concrete ExecutionOrchestrator directly
    container.register(ExecutionOrchestrator, instance=mock)
    return mock


@pytest.fixture
def mock_context_service(container):
    mock = Mock(spec=IGetContextUseCase)
    container.register(IGetContextUseCase, instance=mock)
    # The CLI resolves concrete ContextService directly in some places
    container.register(ContextService, instance=mock)
    return mock


@pytest.fixture
def mock_edit_simulator(container):
    mock = Mock(spec=EditSimulator)
    container.register(EditSimulator, instance=mock)
    return mock


@pytest.fixture
def mock_inspector(container):
    mock = Mock(spec=IEnvironmentInspector)
    container.register(IEnvironmentInspector, instance=mock)
    return mock


@pytest.fixture
def mock_report_formatter(container):
    mock = Mock(spec=IMarkdownReportFormatter)
    container.register(IMarkdownReportFormatter, instance=mock)
    return mock


@pytest.fixture
def mock_llm_client(container):
    mock = Mock(spec=ILlmClient)

    # Create a structured ModelResponse mock
    from unittest.mock import MagicMock

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
