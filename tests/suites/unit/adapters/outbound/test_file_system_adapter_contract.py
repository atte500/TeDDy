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
