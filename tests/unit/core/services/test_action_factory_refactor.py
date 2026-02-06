import punq
import pytest
from unittest.mock import Mock

from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    IWebScraper,
)
from teddy_executor.core.services.action_factory import ActionFactory


@pytest.fixture
def container() -> punq.Container:
    container = punq.Container()
    # Register mocks for BOTH protocols that the factory might resolve.
    # This prevents state leakage between tests by ensuring the container
    # can provide a clean, correctly-specced mock for each interface.
    container.register(IFileSystemManager, instance=Mock(spec=IFileSystemManager))
    container.register(IWebScraper, instance=Mock(spec=IWebScraper))
    return container


@pytest.fixture
def factory(container: punq.Container) -> ActionFactory:
    return ActionFactory(container)


def test_read_action_with_url_resolves_web_scraper(factory: ActionFactory):
    """
    Given an ActionFactory with a WebScraper registered,
    When create_action is called for a 'read' action with a URL parameter,
    Then it should return the WebScraper adapter.
    """
    # Act
    action_handler = factory.create_action("read", {"resource": "http://example.com"})

    # Assert
    assert isinstance(action_handler, Mock)
    assert hasattr(action_handler, "get_content")  # Check if it's a WebScraper mock
    assert not hasattr(action_handler, "read_file")  # Check it's not a FileSystem mock


def test_read_action_with_path_resolves_file_system_manager(factory: ActionFactory):
    """
    Given an ActionFactory with a FileSystemManager registered,
    When create_action is called for a 'read' action with a file path parameter,
    Then it should return the FileSystemManager adapter.
    """
    # Act
    action_handler = factory.create_action("read", {"resource": "path/to/file.txt"})

    # Assert
    assert isinstance(action_handler, Mock)
    assert hasattr(action_handler, "read_file")
    assert not hasattr(action_handler, "get_content")
