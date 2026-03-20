import pytest
from tests.harness.observers.file_system_observer import FileSystemObserver


def test_assert_file_exists_passes_if_exists(tmp_path):
    # Arrange
    file_path = tmp_path / "test.txt"
    file_path.touch()
    observer = FileSystemObserver()

    # Act & Assert
    observer.assert_file_exists(file_path)


def test_assert_file_exists_raises_if_missing(tmp_path):
    # Arrange
    file_path = tmp_path / "missing.txt"
    observer = FileSystemObserver()

    # Act & Assert
    with pytest.raises(AssertionError, match="File missing.txt does not exist"):
        observer.assert_file_exists(file_path)


def test_assert_file_content_equals_passes_if_matches(tmp_path):
    # Arrange
    file_path = tmp_path / "test.txt"
    content = "hello world"
    file_path.write_text(content, encoding="utf-8")
    observer = FileSystemObserver()

    # Act & Assert
    observer.assert_file_content_equals(file_path, content)


def test_assert_file_content_equals_raises_if_differs(tmp_path):
    # Arrange
    file_path = tmp_path / "test.txt"
    file_path.write_text("actual", encoding="utf-8")
    observer = FileSystemObserver()

    # Act & Assert
    with pytest.raises(AssertionError, match="File test.txt content mismatch"):
        observer.assert_file_content_equals(file_path, "expected")


def test_assert_directory_contains_exactly(tmp_path):
    # Arrange
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()
    observer = FileSystemObserver()

    # Act & Assert
    observer.assert_directory_contains(tmp_path, ["a.txt", "b.txt"])


def test_assert_directory_contains_raises_on_mismatch(tmp_path):
    # Arrange
    (tmp_path / "a.txt").touch()
    observer = FileSystemObserver()

    # Act & Assert
    with pytest.raises(AssertionError, match="Directory content mismatch"):
        observer.assert_directory_contains(tmp_path, ["a.txt", "missing.txt"])


def test_assert_file_matches_pattern(tmp_path):
    # Arrange
    file_path = tmp_path / "test.txt"
    file_path.write_text("user_id: 123", encoding="utf-8")
    observer = FileSystemObserver()

    # Act & Assert
    observer.assert_file_matches_pattern(file_path, r"user_id: \d+")
