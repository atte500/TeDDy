from pathlib import Path
import pytest

from teddy.adapters.outbound.file_system_adapter import LocalFileSystemAdapter


def test_create_file_happy_path(tmp_path: Path):
    """
    Given a file path and content,
    When the create_file method is called,
    Then it should create a file with the specified content.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    file_path = tmp_path / "test_file.txt"
    content = "Hello, Teddy!"

    # Act
    adapter.create_file(path=str(file_path), content=content)

    # Assert
    assert file_path.exists(), "File was not created."
    assert file_path.read_text() == content


def test_read_file_happy_path(tmp_path: Path):
    """
    Tests that read_file returns the content of an existing file.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    file_path = tmp_path / "test_file.txt"
    expected_content = "Hello, Teddy Executor!"
    file_path.write_text(expected_content)

    # Act
    content = adapter.read_file(path=str(file_path))

    # Assert
    assert content == expected_content


def test_read_file_raises_error_if_not_exists(tmp_path: Path):
    """
    Tests that read_file raises FileNotFoundError for a non-existent file.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    non_existent_path = tmp_path / "non_existent_file.txt"

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        adapter.read_file(path=str(non_existent_path))
