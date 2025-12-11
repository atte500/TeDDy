from unittest.mock import MagicMock

import pytest

from teddy.core.ports.outbound.file_system_manager import FileSystemManager
from teddy.core.ports.outbound.shell_executor import ShellExecutor
from teddy.core.ports.outbound.web_scraper import WebScraper
from teddy.core.services.action_factory import ActionFactory
from teddy.core.services.plan_service import PlanService


@pytest.fixture
def plan_service_with_mocks():
    """
    Provides a PlanService instance with all its dependencies mocked.
    Yields a tuple containing the service instance and a dict of its mocks.
    """
    mocks = {
        "shell_executor": MagicMock(spec=ShellExecutor),
        "file_system_manager": MagicMock(spec=FileSystemManager),
        "action_factory": MagicMock(spec=ActionFactory),
        "web_scraper": MagicMock(spec=WebScraper),
    }
    plan_service = PlanService(
        shell_executor=mocks["shell_executor"],
        file_system_manager=mocks["file_system_manager"],
        action_factory=mocks["action_factory"],
        web_scraper=mocks["web_scraper"],
    )
    yield plan_service, mocks
