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


def test_remove_file_deletes_existing_file(tmp_path):
    """
    Verifies that remove_file deletes a file from the filesystem.
    """
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))
    file_path = tmp_path / "to_delete.txt"
    file_path.write_text("content")

    # Act
    adapter.remove_file("to_delete.txt")

    # Assert
    assert not file_path.exists()


def test_remove_file_raises_on_nonexistent_file(tmp_path):
    """
    Verifies that remove_file raises FileNotFoundError for missing files.
    """
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))

    # Act / Assert
    with pytest.raises(FileNotFoundError):
        adapter.remove_file("nonexistent.txt")


def test_read_file_bytes_returns_the_exact_payload(tmp_path):
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))
    payload = b"%PDF-1.4\n\xff\x00binary"
    (tmp_path / "doc.pdf").write_bytes(payload)

    # Act / Assert
    assert adapter.read_file_bytes("doc.pdf") == payload


def test_read_file_bytes_raises_for_a_missing_file(tmp_path):
    # Arrange
    simulator = POSIXPathMock(spec=IEditSimulator)
    adapter = LocalFileSystemAdapter(edit_simulator=simulator, root_dir=str(tmp_path))

    # Act / Assert
    with pytest.raises(FileNotFoundError):
        adapter.read_file_bytes("missing.pdf")


@pytest.fixture
def adapter(tmp_path) -> LocalFileSystemAdapter:
    return LocalFileSystemAdapter(
        edit_simulator=POSIXPathMock(spec=IEditSimulator), root_dir=str(tmp_path)
    )


def test_file_system_manager_defines_move_path_and_remove_path():
    # Arrange / Act
    move_path = getattr(IFileSystemManager, "move_path", None)
    remove_path = getattr(IFileSystemManager, "remove_path", None)

    # Assert
    assert callable(move_path), (
        "IFileSystemManager must define move_path(old_path: str, new_path: str) -> None"
    )
    assert callable(remove_path), (
        "IFileSystemManager must define "
        "remove_path(path: str, recursive: bool = False) -> None"
    )


def test_move_path_moves_a_file(adapter, tmp_path):
    # Arrange
    (tmp_path / "old_name.py").write_text("payload", encoding="utf-8")

    # Act
    adapter.move_path("old_name.py", "new_name.py")

    # Assert
    assert not (tmp_path / "old_name.py").exists()
    assert (tmp_path / "new_name.py").read_text(encoding="utf-8") == "payload"


def test_move_path_moves_a_directory_subtree(adapter, tmp_path):
    # Arrange
    (tmp_path / "legacy" / "nested").mkdir(parents=True)
    (tmp_path / "legacy" / "nested" / "module.py").write_text("body", encoding="utf-8")

    # Act
    adapter.move_path("legacy", "current")

    # Assert
    assert not (tmp_path / "legacy").exists()
    moved = tmp_path / "current" / "nested" / "module.py"
    assert moved.read_text(encoding="utf-8") == "body"


def test_move_path_creates_missing_destination_parents(adapter, tmp_path):
    # Arrange
    (tmp_path / "note.md").write_text("text", encoding="utf-8")

    # Act
    adapter.move_path("note.md", "docs/notes/note.md")

    # Assert
    assert (tmp_path / "docs" / "notes" / "note.md").is_file()


def test_move_path_raises_when_source_missing(adapter):
    # Act / Assert
    with pytest.raises(FileNotFoundError):
        adapter.move_path("absent.py", "elsewhere.py")


def test_move_path_raises_when_destination_exists(adapter, tmp_path):
    # Arrange
    (tmp_path / "source.py").write_text("source", encoding="utf-8")
    (tmp_path / "occupied.py").write_text("occupied", encoding="utf-8")

    # Act / Assert
    with pytest.raises(FileExistsError):
        adapter.move_path("source.py", "occupied.py")

    assert (tmp_path / "source.py").read_text(encoding="utf-8") == "source"
    assert (tmp_path / "occupied.py").read_text(encoding="utf-8") == "occupied"


def test_remove_path_removes_a_file(adapter, tmp_path):
    # Arrange
    (tmp_path / "scratch.md").write_text("draft", encoding="utf-8")

    # Act
    adapter.remove_path("scratch.md")

    # Assert
    assert not (tmp_path / "scratch.md").exists()


def test_remove_path_raises_when_path_missing(adapter):
    # Act / Assert
    with pytest.raises(FileNotFoundError):
        adapter.remove_path("absent.md")


def test_remove_path_removes_an_empty_directory_without_recursive(adapter, tmp_path):
    # Arrange
    (tmp_path / "empty").mkdir()

    # Act
    adapter.remove_path("empty")

    # Assert
    assert not (tmp_path / "empty").exists()


def test_remove_path_refuses_a_non_empty_directory_without_recursive(adapter, tmp_path):
    # Arrange
    (tmp_path / "legacy").mkdir()
    (tmp_path / "legacy" / "module.py").write_text("body", encoding="utf-8")

    # Act / Assert
    with pytest.raises(OSError):
        adapter.remove_path("legacy")

    assert (tmp_path / "legacy" / "module.py").exists()


def test_remove_path_removes_a_non_empty_directory_recursively(adapter, tmp_path):
    # Arrange
    (tmp_path / "legacy" / "nested").mkdir(parents=True)
    (tmp_path / "legacy" / "nested" / "module.py").write_text("body", encoding="utf-8")

    # Act
    adapter.remove_path("legacy", recursive=True)

    # Assert
    assert not (tmp_path / "legacy").exists()


def test_remove_path_recursively_removes_ignored_files(adapter, tmp_path):
    # Arrange: the ignore spec must not shield a file from an explicit removal.
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (tmp_path / "legacy").mkdir()
    (tmp_path / "legacy" / "debug.log").write_text("noise", encoding="utf-8")

    # Act
    adapter.remove_path("legacy", recursive=True)

    # Assert
    assert not (tmp_path / "legacy").exists()
