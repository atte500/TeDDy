import pytest
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def test_rename_session_moves_directory(env):
    """
    Verify that rename_session renames the directory on the filesystem.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    mock_fs.path_exists.side_effect = lambda p: p == ".teddy/sessions/old-name"

    # Act
    new_path = service.rename_session("old-name", "new-name")

    # Assert
    assert new_path == ".teddy/sessions/new-name"
    mock_fs.move_directory.assert_called_once_with(
        ".teddy/sessions/old-name", ".teddy/sessions/new-name"
    )


def test_rename_session_raises_if_not_found(env):
    """
    Verify that renaming a non-existent session raises ValueError.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    mock_fs.path_exists.return_value = False

    # Act & Assert
    with pytest.raises(ValueError, match="Session 'missing' not found."):
        service.rename_session("missing", "new")


def test_rename_session_raises_if_target_exists(env):
    """
    Verify that renaming to an existing session name raises ValueError.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    mock_fs.path_exists.return_value = True

    # Act & Assert
    with pytest.raises(ValueError, match="Session 'new' already exists."):
        service.rename_session("old", "new")
