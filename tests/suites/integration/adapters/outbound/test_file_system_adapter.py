from pathlib import Path
import pytest

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.observers.file_system_observer import FileSystemObserver
from teddy_executor.core.domain.models import (
    MultipleMatchesFoundError,
    FileAlreadyExistsError,
    SearchTextNotFoundError,
)
from teddy_executor.core.ports.outbound import IFileSystemManager


@pytest.fixture
def observer():
    return FileSystemObserver()


@pytest.fixture
def adapter(monkeypatch, tmp_path: Path):
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    return env.get_service(IFileSystemManager)  # type: ignore[type-abstract]


def test_create_file_raises_custom_error_if_file_exists(adapter, tmp_path: Path):
    file_path = tmp_path / "existing_file.txt"
    file_path.write_text("initial content", encoding="utf-8")

    with pytest.raises(FileAlreadyExistsError) as excinfo:
        adapter.create_file(path=str(file_path), content="new content")

    assert excinfo.value.file_path == str(file_path)


def test_create_file_creates_parent_directories(adapter, observer, tmp_path: Path):
    new_file_path = "new_dir/sub_dir/test.txt"
    full_path = tmp_path / new_file_path
    assert not full_path.parent.exists()

    adapter.create_file(path=str(full_path), content="content")
    observer.assert_file_content_equals(full_path, "content")


def test_create_file_happy_path(adapter, observer, tmp_path: Path):
    file_path = tmp_path / "test_file.txt"
    content = "Hello, Teddy!"

    adapter.create_file(path=str(file_path), content=content)
    observer.assert_file_content_equals(file_path, content)


def test_read_file_happy_path(adapter, tmp_path: Path):
    """
    Tests that read_file returns the content of an existing file.
    """
    # Arrange
    file_path = tmp_path / "test_file.txt"
    expected_content = "Hello, Teddy Executor!"
    file_path.write_text(expected_content, encoding="utf-8")

    # Act
    content = adapter.read_file(path=str(file_path))

    # Assert
    assert content == expected_content


def test_read_file_raises_error_if_not_exists(adapter, tmp_path: Path):
    """
    Tests that read_file raises FileNotFoundError for a non-existent file.
    """
    # Arrange
    non_existent_path = tmp_path / "non_existent_file.txt"

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        adapter.read_file(path=str(non_existent_path))


def test_edit_file_successfully_replaces_content(adapter, observer, tmp_path: Path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello world, this is a test.", encoding="utf-8")

    adapter.edit_file(
        path=str(test_file), edits=[{"find": "world", "replace": "TeDDy"}]
    )
    observer.assert_file_content_equals(test_file, "Hello TeDDy, this is a test.")


def test_edit_file_handles_multiline_replacement(adapter, observer, tmp_path: Path):
    test_file = tmp_path / "code.py"
    test_file.write_text("def foo():\n    return 42\n", encoding="utf-8")

    find_block = "def foo():\n    return 42"
    replace_block = "def bar(x):\n    return x * 2"
    adapter.edit_file(
        path=str(test_file), edits=[{"find": find_block, "replace": replace_block}]
    )
    observer.assert_file_content_equals(test_file, "def bar(x):\n    return x * 2\n")


def test_edit_file_removes_newline_on_empty_replacement(
    adapter, observer, tmp_path: Path
):
    test_file = tmp_path / "lines.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3\n", encoding="utf-8")

    adapter.edit_file(path=str(test_file), edits=[{"find": "Line 2", "replace": ""}])
    observer.assert_file_content_equals(test_file, "Line 1\nLine 3\n")


def test_edit_file_raises_error_if_find_text_not_found(adapter, tmp_path: Path):
    test_file = tmp_path / "test.txt"
    initial_content = "Hello world, this is a test."
    test_file.write_text(initial_content, encoding="utf-8")

    with pytest.raises(SearchTextNotFoundError) as excinfo:
        adapter.edit_file(
            path=str(test_file), edits=[{"find": "goodbye", "replace": "TeDDy"}]
        )

    assert excinfo.value.content == initial_content


def test_edit_file_raises_error_on_multiple_occurrences(adapter, tmp_path: Path):
    test_file = tmp_path / "test.txt"
    original_content = "hello world, hello again"
    test_file.write_text(original_content, encoding="utf-8")

    with pytest.raises(MultipleMatchesFoundError) as exc_info:
        adapter.edit_file(
            path=str(test_file), edits=[{"find": "hello", "replace": "goodbye"}]
        )

    assert "Found 2 ambiguous occurrences of 'hello'" in str(exc_info.value)
    assert exc_info.value.content == original_content
    assert test_file.read_text() == original_content


def test_path_exists(adapter, tmp_path: Path):
    existing_file = tmp_path / "exists.txt"
    existing_file.touch()
    assert adapter.path_exists(str(existing_file)) is True
    assert adapter.path_exists(str(tmp_path / "not_exists.txt")) is False


def test_create_directory(adapter, tmp_path: Path):
    new_dir = tmp_path / "new" / "nested" / "dir"
    adapter.create_directory(str(new_dir))
    assert new_dir.is_dir()


def test_write_file(adapter, observer, tmp_path: Path):
    file_path = tmp_path / "test.txt"

    adapter.write_file(str(file_path), "first content")
    observer.assert_file_content_equals(file_path, "first content")

    adapter.write_file(str(file_path), "second content")
    observer.assert_file_content_equals(file_path, "second content")


def test_read_files_in_vault(adapter, tmp_path: Path):
    """
    Tests that read_files_in_vault reads content for existing files
    and ignores non-existent files.
    """
    # Arrange
    (tmp_path / "file1.txt").write_text("content1", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "file2.txt").write_text("content2", encoding="utf-8")

    paths_to_read = ["file1.txt", "docs/file2.txt", "non_existent_file.txt"]

    expected_contents = {
        "file1.txt": "content1",
        "docs/file2.txt": "content2",
        "non_existent_file.txt": None,
    }

    # Act
    actual_contents = adapter.read_files_in_vault(paths_to_read)

    # Assert
    assert actual_contents == expected_contents


def test_resolve_paths_from_files_returns_sorted_deduplicated_paths(adapter, tmp_path):
    """
    Tests that resolve_paths_from_files reads multiple files,
    strips comments/whitespace, and returns a unique sorted list of paths.
    """
    # Arrange
    file1 = tmp_path / "file1.context"
    file1.write_text("path/a\n# comment\n  path/b  \n", encoding="utf-8")

    file2 = tmp_path / "file2.context"
    file2.write_text("path/b\npath/c\n\n", encoding="utf-8")

    # Act
    result = adapter.resolve_paths_from_files([str(file1), str(file2)])

    # Assert
    assert result == ["path/a", "path/b", "path/c"]


def test_get_context_paths(adapter, tmp_path: Path):
    """
    Tests that get_context_paths finds all .context files, reads them,
    and returns a sorted, deduplicated list of non-commented paths.
    """
    # Arrange
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()

    (teddy_dir / "init.context").write_text("file1.py\n# comment\nfile2.py\nfile1.py")
    (teddy_dir / "temp.context").write_text("file3.py\n\nfile4.py")
    (teddy_dir / "other.txt").write_text("not_a_context_file.py")

    expected_paths = sorted(["file1.py", "file2.py", "file3.py", "file4.py"])

    # Act
    actual_paths = adapter.get_context_paths()

    # Assert
    assert actual_paths == expected_paths


def test_edit_file_handles_leading_newline_in_find_block(
    adapter, observer, tmp_path: Path
):
    test_file = tmp_path / "test.txt"
    test_file.write_text("line one\n\n    line two\nline three", encoding="utf-8")

    find_block = "line one\n\n    line two"
    replace_block = "line one\n\n    line two (replaced)"
    adapter.edit_file(
        path=str(test_file), edits=[{"find": find_block, "replace": replace_block}]
    )
    observer.assert_file_content_equals(
        test_file, "line one\n\n    line two (replaced)\nline three"
    )
