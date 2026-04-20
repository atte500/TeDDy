from unittest.mock import MagicMock
from teddy_executor.core.services.session_repository import SessionRepository


def test_resolve_session_from_path_strips_timestamp_prefix():
    # Setup
    mock_fs = MagicMock()
    repo = SessionRepository(mock_fs)

    # Path inside a prefixed session folder
    path = ".teddy/sessions/20260417_120000-my-feature/01/plan.md"

    # Act
    session_name = repo.resolve_session_from_path(path)

    # Assert
    assert session_name == "my-feature"


def test_get_latest_session_name_strips_timestamp_prefix():
    # Setup
    mock_fs = MagicMock()
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.return_value = [
        "20260417_120000-feat-a",
        "20260417_120001-feat-b",
    ]
    mock_fs.get_mtime.side_effect = [100, 200]

    repo = SessionRepository(mock_fs)

    # Act
    session_name = repo.get_latest_session_name()

    # Assert
    assert session_name == "feat-b"
