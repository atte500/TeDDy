import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_service import SessionService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_fs():
    return MagicMock(spec=IFileSystemManager)


@pytest.fixture
def service(mock_fs):
    return SessionService(mock_fs)


def test_get_latest_session_name_returns_most_recent(service, mock_fs):
    """Should sort sessions by mtime and return the latest."""
    mock_fs.list_directory.return_value = ["old-session", "new-session"]
    # Mocking mtime: new-session is newer
    mock_fs.get_mtime.side_effect = lambda p: 2000 if "new-session" in p else 1000
    mock_fs.path_exists.return_value = True

    assert service.get_latest_session_name() == "new-session"


def test_resolve_session_from_path_with_session_root(service, mock_fs):
    """Should return session name if path points to session root."""
    path = ".teddy/sessions/my-session"
    mock_fs.path_exists.return_value = True
    # Simulate directory structure check
    # In reality we might just check if it's inside .teddy/sessions
    assert service.resolve_session_from_path(path) == "my-session"


def test_resolve_session_from_path_with_turn_dir(service, mock_fs):
    """Should return session name if path points to a turn directory."""
    path = ".teddy/sessions/my-session/01"
    mock_fs.path_exists.return_value = True
    assert service.resolve_session_from_path(path) == "my-session"


def test_resolve_session_from_path_with_file(service, mock_fs):
    """Should return session name if path points to a file inside a turn."""
    path = ".teddy/sessions/my-session/01/meta.yaml"
    mock_fs.path_exists.return_value = True
    assert service.resolve_session_from_path(path) == "my-session"
