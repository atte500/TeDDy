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


def test_edit_file_successfully_replaces_content(tmp_path: Path):
    """
    Tests that edit_file correctly finds and replaces content in an existing file.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    test_file = tmp_path / "test.txt"
    initial_content = "Hello world, this is a test."
    test_file.write_text(initial_content)

    # Act
    adapter.edit_file(path=str(test_file), find="world", replace="TeDDy")

    # Assert
    final_content = test_file.read_text()
    assert final_content == "Hello TeDDy, this is a test."


def test_edit_file_raises_error_if_find_text_not_found(tmp_path: Path):
    """
    Tests that edit_file raises a specific error if the search text is not found.
    """
    # Arrange
    from teddy.core.domain.models import SearchTextNotFoundError

    adapter = LocalFileSystemAdapter()
    test_file = tmp_path / "test.txt"
    initial_content = "Hello world, this is a test."
    test_file.write_text(initial_content)

    # Act & Assert
    with pytest.raises(SearchTextNotFoundError) as excinfo:
        adapter.edit_file(path=str(test_file), find="goodbye", replace="TeDDy")

    # Assert that the original content is part of the exception
    assert excinfo.value.content == initial_content
