from pathlib import Path

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
