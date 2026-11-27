import pytest

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.services.web_content_service import WebContentService
from tests.harness.setup.fake_web_content_cache import FakeWebContentCache
from tests.harness.setup.fake_web_scraper import FakeWebScraper

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


def test_read_action_with_url_resolves_the_coordinator(
    mock_shell, mock_fs, mock_user_interactor, mock_searcher, mock_config
):
    """
    Given an ActionFactory wired to a WebContentService,
    When a URL READ is created with a session root,
    Then the handler resolves through the coordinator and caches the body.
    """
    # Arrange
    url = "http://example.com"
    body = "web content"
    session_root = ".teddy/sessions/demo/first"
    scraper = FakeWebScraper(contents={url: body})
    cache = FakeWebContentCache()
    factory = ActionFactory(
        ActionPorts(
            shell_executor=mock_shell,
            file_system_manager=mock_fs,
            user_interactor=mock_user_interactor,
            web_searcher=mock_searcher,
            config_service=mock_config,
        ),
        web_content_service=WebContentService(
            web_scraper=scraper, cache=cache, config_service=mock_config
        ),
    )

    # Act
    action_handler = factory.create_action(
        "read", {"resource": url}, session_root=session_root
    )
    result = action_handler.execute(path=url)

    # Assert
    assert result == body
    assert scraper.calls == [(url, {})], (
        "a URL read must resolve through the coordinator, which fetches the body"
    )
    assert cache.merge_calls == [(session_root, {url: body})]


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


def test_move_action_resolves_file_system_manager(mock_fs, factory: ActionFactory):
    """
    Given a MOVE action type,
    When create_action is called,
    Then the handler invokes the filesystem port's move primitive.
    """
    # Arrange
    handler = factory.create_action(
        "MOVE", {"source": "app/old.py", "destination": "app/new.py"}
    )

    # Act
    handler.execute(old_path="app/old.py", new_path="app/new.py")

    # Assert
    mock_fs.move_path.assert_called_once_with(
        old_path="app/old.py", new_path="app/new.py"
    )


def test_delete_action_resolves_file_system_manager(mock_fs, factory: ActionFactory):
    """
    Given a DELETE action type,
    When create_action is called,
    Then the handler invokes the filesystem port's removal primitive.
    """
    # Arrange
    handler = factory.create_action("DELETE", {"path": "app/legacy"})

    # Act
    handler.execute(path="app/legacy", recursive=False)

    # Assert
    mock_fs.remove_path.assert_called_once_with(path="app/legacy", recursive=False)
