import pytest
import punq

from teddy_executor.core.services.action_factory import ActionFactory

# --- Fixtures ---


@pytest.fixture
def factory(container: punq.Container) -> ActionFactory:
    """Provides an ActionFactory instance with the centralized container."""
    return ActionFactory(container=container)


# --- Test Cases ---


def test_create_action_successfully_resolves_handler(
    mock_shell, factory: ActionFactory
):
    """
    Given a known action type ('execute'),
    When create_action is called,
    Then it should resolve and return the correct handler from the container.
    """
    # Arrange
    action_type = "execute"

    # Act
    action_handler = factory.create_action(action_type)

    # Assert
    assert action_handler is mock_shell


def test_create_action_raises_error_for_unknown_type(factory: ActionFactory):
    """
    Given an unknown action type,
    When create_action is called,
    Then it should raise a ValueError.
    """
    # Arrange
    action_type = "non_existent_action"

    # Act & Assert
    with pytest.raises(ValueError, match="Unknown action type: 'non_existent_action'"):
        factory.create_action(action_type)


def test_create_action_for_return_returns_handler(factory: ActionFactory):
    """
    Given the 'RETURN' action type,
    When create_action is called,
    Then it should return a ConcludeAction handler.
    """
    # Arrange
    from teddy_executor.core.services.action_factory import ConcludeAction

    action_type = "RETURN"

    # Act
    action_handler = factory.create_action(action_type)

    # Assert
    assert isinstance(action_handler, ConcludeAction)


def test_read_action_with_url_resolves_web_scraper(
    mock_scraper, factory: ActionFactory
):
    """
    Given an ActionFactory with a WebScraper registered,
    When create_action is called for a 'read' action with a URL parameter,
    Then it should return the WebScraper adapter.
    """
    # Act
    action_handler = factory.create_action("read", {"resource": "http://example.com"})

    # Assert
    assert action_handler is mock_scraper


def test_read_action_with_path_resolves_file_system_manager(
    mock_fs, factory: ActionFactory
):
    """
    Given an ActionFactory with a IFileSystemManager registered,
    When create_action is called for a 'read' action with a file path parameter,
    Then it should return the IFileSystemManager adapter.
    """
    # Act
    action_handler = factory.create_action("read", {"resource": "path/to/file.txt"})

    # Assert
    assert action_handler is mock_fs
