import pytest

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from tests.harness.setup.mocking import POSIXPathMock


def test_is_dir_returns_true_for_directory(tmp_path):
    # Arrange
    mock_simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=mock_simulator)
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()

    # Act & Assert
    assert adapter.is_dir(str(dir_path)) is True


def test_is_dir_returns_false_for_file(tmp_path):
    # Arrange
    mock_simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=mock_simulator)
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("content")

    # Act & Assert
    assert adapter.is_dir(str(file_path)) is False


def test_is_dir_returns_false_for_non_existent_path():
    # Arrange
    mock_simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=mock_simulator)

    # Act & Assert
    assert adapter.is_dir("non_existent_path_999") is False


def test_file_system_manager_defines_create_directory_exclusive():
    # Arrange / Act
    method = getattr(IFileSystemManager, "create_directory_exclusive", None)

    # Assert
    assert callable(method), (
        "IFileSystemManager must define create_directory_exclusive(path: str) -> bool"
    )


def test_create_directory_exclusive_returns_true_on_fresh_create(tmp_path):
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))

    # Act
    result = adapter.create_directory_exclusive("fresh_session")

    # Assert
    assert result is True
    assert (tmp_path / "fresh_session").is_dir()


def test_create_directory_exclusive_returns_false_when_already_exists(tmp_path):
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))
    (tmp_path / "occupied").mkdir()

    # Act
    result = adapter.create_directory_exclusive("occupied")

    # Assert
    assert result is False


def test_create_directory_exclusive_creates_parent_directories(tmp_path):
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))

    # Act
    result = adapter.create_directory_exclusive("a/b/c")

    # Assert
    assert result is True
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_create_directory_exclusive_reraises_non_file_exists_errors(tmp_path):
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))

    # Act / Assert: embedded NUL raises ValueError deterministically on all
    # platforms (unlike NotADirectoryError, which Windows maps toward
    # FileExistsError). Non-FileExistsError errors MUST be re-raised.
    with pytest.raises(ValueError):
        adapter.create_directory_exclusive("bad\x00path")
