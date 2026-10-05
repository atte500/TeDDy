from unittest.mock import create_autospec
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.services.session_repository import SessionRepository


def test_resolve_session_from_path_returns_full_folder_name():
    # Setup
    mock_fs = create_autospec(IFileSystemManager, instance=True)
    repo = SessionRepository(mock_fs)

    # Path inside a prefixed session folder
    path = ".teddy/sessions/20260417_120000-feature/01/plan.md"

    # Act
    session_name = repo.resolve_session_from_path(path)

    # Assert
    assert session_name == "20260417_120000-feature"


def test_get_latest_session_name_returns_full_folder_name():
    # Setup
    mock_fs = create_autospec(IFileSystemManager, instance=True)
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
    assert session_name == "20260417_120001-feat-b"


def test_read_context_file_filters_comments_and_strips_whitespace():
    # Setup
    mock_fs = create_autospec(IFileSystemManager, instance=True)
    repo = SessionRepository(mock_fs)

    content = (
        "file1.py\n"
        "  file2.py  \n"
        "# commented/path.py\n"
        "   # another/comment.py\n"
        "\n"
        "valid/path.txt"
    )
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    # Act
    paths = repo.read_context_file("any.context")

    # Assert
    assert "file1.py" in paths
    assert "file2.py" in paths
    assert "valid/path.txt" in paths
    assert "# commented/path.py" not in paths
    assert "commented/path.py" not in paths
    assert "# another/comment.py" not in paths
    assert "" not in paths
    assert paths == {"file1.py", "file2.py", "valid/path.txt"}


def test_get_latest_turn_returns_numerically_latest_turn():
    # Arrange: a session whose turns run from 01 through 100 (crosses the
    # two-digit boundary that breaks lexicographic ordering).
    file_system_manager = create_autospec(IFileSystemManager, instance=True)
    file_system_manager.list_directory.return_value = [
        f"{turn:02d}" for turn in range(1, 101)
    ]
    repository = SessionRepository(file_system_manager)

    # Act
    latest_turn = repository.get_latest_turn("feat-x")

    # Assert: the numerically-latest turn (100), not the lexicographic "99".
    assert latest_turn == ".teddy/sessions/feat-x/100"
