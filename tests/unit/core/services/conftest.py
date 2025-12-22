from unittest.mock import MagicMock
import pytest
from teddy.core.ports.outbound.file_system_manager import FileSystemManager
from teddy.core.ports.outbound.shell_executor import ShellExecutor
from teddy.core.ports.outbound.user_interactor import UserInteractor
from teddy.core.ports.outbound.web_scraper import WebScraper
from teddy.core.services.action_factory import ActionFactory
from teddy.core.services.plan_service import PlanService


@pytest.fixture
def mock_shell_executor():
    """Provides a MagicMock for the ShellExecutor port."""
    return MagicMock(spec=ShellExecutor)


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
    """Provides a MagicMock for the UserInteractor port."""
    return MagicMock(spec=UserInteractor)


@pytest.fixture
def plan_service(
    mock_shell_executor,
    mock_file_system_manager,
    mock_action_factory,
    mock_web_scraper,
    mock_user_interactor,
):
    """Provides a PlanService instance with all its dependencies mocked."""
    return PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
        web_scraper=mock_web_scraper,
        user_interactor=mock_user_interactor,
    )
