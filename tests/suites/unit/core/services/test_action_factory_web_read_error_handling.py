"""
Regression test for WebReadAction error handling.
Ensures that when the scraper raises an exception, the action returns
a user-friendly error string instead of propagating the raw exception.
"""

import pytest

from tests.harness.setup.mocking import register_mock
from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.web_searcher import IWebSearcher
from teddy_executor.core.services.action_factory import ActionFactory


class _MockContainer:
    """Minimal container that stores registered instances for register_mock."""

    def __init__(self):
        self._registry: dict = {}

    def register(self, port_type, instance) -> None:
        self._registry[port_type] = instance


@pytest.fixture
def container():
    """Return a dummy container that satisfies register_mock's signature."""
    return _MockContainer()


def test_web_read_action_catches_scraper_exceptions(container: _MockContainer):
    """
    GIVEN a WebReadAction created via ActionFactory with a scraper that raises
    WHEN its execute method is called
    THEN the exception is caught and a user-friendly error string is returned.
    """
    # Prepare an auto-specced mock scraper that raises an exception
    mock_scraper = register_mock(container, WebScraper)
    mock_scraper.get_content.side_effect = RuntimeError("Simulated fetch failure")

    # Build ActionPorts with the mock scraper and minimal mocks for other dependencies
    mock_config = register_mock(container, IConfigService)
    mock_config.get_setting.return_value = None

    ports = ActionPorts(
        shell_executor=register_mock(container, IShellExecutor),
        file_system_manager=register_mock(container, IFileSystemManager),
        user_interactor=register_mock(container, IUserInteractor),
        web_scraper=mock_scraper,
        web_searcher=register_mock(container, IWebSearcher),
        config_service=mock_config,
    )

    factory = ActionFactory(ports)
    action = factory.create_action("read", {"path": "http://example.com/403"})

    # Execute the action — should NOT raise; returns error string
    result = action.execute(path="http://example.com/403")

    # Assert the result is a user-friendly error message
    assert isinstance(result, str), f"Expected string, got {type(result)}"
    assert "Error" in result, f"Expected error message, got: {result}"
    assert "Simulated fetch failure" in result
