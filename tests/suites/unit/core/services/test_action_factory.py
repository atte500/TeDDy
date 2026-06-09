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


def test_read_action_with_lines_extracts_range(
    mock_fs,
    mock_scraper,
    factory: ActionFactory,
):
    """
    Verifies that a READ action with a Lines parameter uses read_raw_file
    (bypassing truncation) and extracts only the requested line range.
    """
    # Arrange
    action_type = "READ"
    file_path = "src/data.txt"
    params = {"resource": file_path, "path": file_path, "lines": "2-4"}

    multi_line_content = "line1\nline2\nline3\nline4\nline5"
    mock_fs.read_raw_file.return_value = multi_line_content

    # Act
    handler = factory.create_action(action_type, params)
    result = handler.execute(**params)

    # Assert
    # read_raw_file should be called (bypasses truncation)
    mock_fs.read_raw_file.assert_called_once_with(path=file_path)
    # read_file should NOT be called (it adds head truncation)
    mock_fs.read_file.assert_not_called()
    # Result should be only lines 2-4
    assert result == "line2\nline3\nline4", f"Expected lines 2-4, got: {result}"
