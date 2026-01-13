from unittest.mock import MagicMock
import pytest
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from teddy_executor.core.ports.outbound.user_interactor import UserInteractor
from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.web_searcher import IWebSearcher
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.services.plan_service import PlanService


@pytest.fixture
def mock_shell_executor():
    """Provides a MagicMock for the IShellExecutor port."""
    return MagicMock(spec=IShellExecutor)


@pytest.fixture
def mock_file_system_manager():
    """Provides a MagicMock for the FileSystemManager port."""
    return MagicMock(spec=FileSystemManager)


@pytest.fixture
def mock_action_factory():
    """Provides a MagicMock for the ActionFactory service."""
    return MagicMock(spec=ActionFactory)


@pytest.fixture
def mock_web_scraper():
    """Provides a MagicMock for the WebScraper port."""
    return MagicMock(spec=WebScraper)


@pytest.fixture
def mock_user_interactor():
    """
    Provides a MagicMock for the UserInteractor port, with a default
    approval for confirm_action to support existing tests.
    """
    mock = MagicMock(spec=UserInteractor)
    mock.confirm_action.return_value = (True, "")
    return mock


@pytest.fixture
def mock_web_searcher():
    """Provides a MagicMock for the IWebSearcher port."""
    return MagicMock(spec=IWebSearcher)


@pytest.fixture
def plan_service(
    mock_shell_executor,
    mock_file_system_manager,
    mock_action_factory,
    mock_web_scraper,
    mock_user_interactor,
    mock_web_searcher,
):
    """Provides a PlanService instance with all its dependencies mocked."""
    return PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
        web_scraper=mock_web_scraper,
        user_interactor=mock_user_interactor,
        web_searcher=mock_web_searcher,
    )
