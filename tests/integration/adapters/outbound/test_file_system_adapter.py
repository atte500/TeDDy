from pathlib import Path
import pytest


from teddy_executor.core.domain.models import MultipleMatchesFoundError
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)


def test_create_file_raises_custom_error_if_file_exists(tmp_path: Path):
    """
    Tests that create_file raises FileAlreadyExistsError when the file
    already exists, and that the exception contains the file path.
    """
    from teddy_executor.core.domain.models import FileAlreadyExistsError

    # Arrange
    adapter = LocalFileSystemAdapter()
    file_path = tmp_path / "existing_file.txt"
    file_path.write_text("initial content", encoding="utf-8")

    # Act & Assert
    with pytest.raises(FileAlreadyExistsError) as excinfo:
        adapter.create_file(path=str(file_path), content="new content")

    assert excinfo.value.file_path == str(file_path)


def test_create_file_creates_parent_directories(tmp_path: Path):
    """
    Verifies that create_file successfully creates necessary parent directories
    for the target file.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    new_file_path = "new_dir/sub_dir/test.txt"
    full_path = tmp_path / new_file_path

    # Pre-condition: Assert that the parent directory does not exist yet
    assert not full_path.parent.exists()

    # Act
    adapter.create_file(path=str(full_path), content="content")

    # Assert
    assert full_path.exists()
    assert full_path.read_text() == "content"


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
    file_path.write_text(expected_content, encoding="utf-8")

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
    test_file.write_text(initial_content, encoding="utf-8")

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
    from teddy_executor.core.domain.models import SearchTextNotFoundError

    adapter = LocalFileSystemAdapter()
    test_file = tmp_path / "test.txt"
    initial_content = "Hello world, this is a test."
    test_file.write_text(initial_content, encoding="utf-8")

    # Act & Assert
    with pytest.raises(SearchTextNotFoundError) as excinfo:
        adapter.edit_file(path=str(test_file), find="goodbye", replace="TeDDy")

    # Assert that the original content is part of the exception
    assert excinfo.value.content == initial_content


def test_edit_file_raises_error_on_multiple_occurrences(tmp_path: Path):
    """
    Tests that edit_file raises MultipleMatchesFoundError if the `find` string
    has more than one occurrence.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    test_file = tmp_path / "test.txt"
    original_content = "hello world, hello again"
    test_file.write_text(original_content, encoding="utf-8")

    # Act & Assert
    with pytest.raises(MultipleMatchesFoundError) as exc_info:
        adapter.edit_file(path=str(test_file), find="hello", replace="goodbye")

    # Check the exception details (the repr() adds extra quotes)
    assert "Found 2 occurrences of ''hello''" in str(exc_info.value)
    assert exc_info.value.content == original_content

    # Verify the file was not changed
    content_after = test_file.read_text()
    assert content_after == original_content


def test_path_exists(tmp_path: Path):
    """
    Tests that path_exists correctly reports the existence of a file.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    existing_file = tmp_path / "exists.txt"
    existing_file.touch()
    non_existing_file = tmp_path / "not_exists.txt"

    # Act & Assert
    assert adapter.path_exists(str(existing_file)) is True
    assert adapter.path_exists(str(non_existing_file)) is False


def test_create_directory(tmp_path: Path):
    """
    Tests that create_directory creates a directory, including parents.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    new_dir = tmp_path / "new" / "nested" / "dir"

    # Act
    adapter.create_directory(str(new_dir))

    # Assert
    assert new_dir.is_dir()


def test_write_file(tmp_path: Path):
    """
    Tests that write_file creates a file if it doesn't exist,
    and overwrites it if it does.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    file_path = tmp_path / "test.txt"

    # Act (Create)
    adapter.write_file(str(file_path), "first content")

    # Assert (Create)
    assert file_path.read_text() == "first content"

    # Act (Overwrite)
    adapter.write_file(str(file_path), "second content")

    # Assert (Overwrite)
    assert file_path.read_text() == "second content"


def test_read_files_in_vault(tmp_path: Path):
    """
    Tests that read_files_in_vault reads content for existing files
    and ignores non-existent files.
    """
    # Arrange
    adapter = LocalFileSystemAdapter(root_dir=str(tmp_path))
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


def test_get_context_paths(tmp_path: Path):
    """
    Tests that get_context_paths finds all .context files, reads them,
    and returns a sorted, deduplicated list of non-commented paths.
    """
    # Arrange
    adapter = LocalFileSystemAdapter(root_dir=str(tmp_path))
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()

    (teddy_dir / "global.context").write_text("file1.py\n# comment\nfile2.py\nfile1.py")
    (teddy_dir / "temp.context").write_text("file3.py\n\nfile4.py")
    (teddy_dir / "other.txt").write_text("not_a_context_file.py")

    expected_paths = sorted(["file1.py", "file2.py", "file3.py", "file4.py"])

    # Act
    actual_paths = adapter.get_context_paths()

    # Assert
    assert actual_paths == expected_paths


def test_edit_file_handles_leading_newline_in_find_block(tmp_path: Path):
    """
    Tests that edit_file can literally match a find block that includes a
    leading newline, which was a previously failing case.
    """
    # Arrange
    adapter = LocalFileSystemAdapter()
    test_file = tmp_path / "test.txt"
    original_content = "line one\n\n    line two\nline three"
    test_file.write_text(original_content, encoding="utf-8")

    # This find block is a literal match of a blank line and an indented line.
    # The previous buggy implementation would .strip() this and fail to find it.
    find_block = "\n    line two"
    replace_block = "\n    line two (replaced)"
    expected_content = "line one\n\n    line two (replaced)\nline three"

    # Act
    adapter.edit_file(path=str(test_file), find=find_block, replace=replace_block)

    # Assert
    actual_content = test_file.read_text()
    assert actual_content == expected_content


def test_create_default_context_file(tmp_path: Path):
    """
    Tests that create_default_context_file creates the .teddy/global.context
    file with the correct, simplified default content.
    """
    # Arrange
    adapter = LocalFileSystemAdapter(root_dir=str(tmp_path))
    expected_file = tmp_path / ".teddy" / "global.context"
    expected_content = "README.md\ndocs/ARCHITECTURE.md\n"

    # Act
    adapter.create_default_context_file()

    # Assert
    assert expected_file.exists()
    assert expected_file.read_text() == expected_content
