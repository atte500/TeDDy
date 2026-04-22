import pytest

from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.domain.models.action_ports import ActionPorts

# --- Fixtures ---


@pytest.fixture
def factory(  # noqa: PLR0913
    mock_shell,
    mock_fs,
    mock_user_interactor,
    mock_scraper,
    mock_searcher,
    mock_config,
) -> ActionFactory:
    """Provides an ActionFactory instance with explicit dependencies."""
    ports = ActionPorts(
        shell_executor=mock_shell,
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        web_scraper=mock_scraper,
        web_searcher=mock_searcher,
        config_service=mock_config,
    )
    return ActionFactory(ports)


# --- Test Cases ---


def test_create_action_successfully_resolves_handler(
    mock_shell, factory: ActionFactory
):
    """
    Given a known action type ('execute'),
    When create_action is called,
    Then it should resolve and return a handler that calls the correct port.
    """
    # Arrange
    action_type = "execute"
    mock_shell.execute.return_value = "success"

    # Act
    action_handler = factory.create_action(action_type)
    result = action_handler.execute(command="echo test")

    # Assert
    assert result == "success"
    mock_shell.execute.assert_called_once()


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
    Then it should return a handler that calls the WebScraper.
    """
    # Arrange
    mock_scraper.get_content.return_value = "web content"

    # Act
    action_handler = factory.create_action("read", {"resource": "http://example.com"})
    result = action_handler.execute(path="http://example.com")

    # Assert
    assert result == "web content"
    mock_scraper.get_content.assert_called_once_with(url="http://example.com")


def test_read_action_with_path_resolves_file_system_manager(
    mock_fs, factory: ActionFactory
):
    """
    Given an ActionFactory with a IFileSystemManager registered,
    When create_action is called for a 'read' action with a file path parameter,
    Then it should return a handler that calls the IFileSystemManager.
    """
    # Arrange
    mock_fs.read_file.return_value = "file content"

    # Act
    action_handler = factory.create_action("read", {"resource": "path/to/file.txt"})
    result = action_handler.execute(path="path/to/file.txt")

    # Assert
    assert result == "file content"
    mock_fs.read_file.assert_called_once_with(path="path/to/file.txt")
