import pytest
from unittest.mock import create_autospec
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator


@pytest.fixture
def edit_simulator():
    return create_autospec(IEditSimulator, instance=True)


def test_read_file_truncates_at_head_when_limit_exceeded(tmp_path, edit_simulator):
    # Arrange
    max_lines = 3
    adapter = LocalFileSystemAdapter(
        edit_simulator=edit_simulator, root_dir=str(tmp_path), max_read_lines=max_lines
    )

    file_path = tmp_path / "large_file.txt"
    content = "line1\nline2\nline3\nline4\nline5"
    file_path.write_text(content, encoding="utf-8")

    # Act
    result = adapter.read_file("large_file.txt")

    # Assert
    # Should contain first 3 lines and the hint
    expected_hint = "[Content truncated: Showing first 3 of 5 lines. Use the 'Lines' parameter to read specific line ranges (e.g., '2-25').]"
    assert result.startswith("line1\nline2\nline3")
    assert expected_hint in result
    assert "line4" not in result
    assert "line5" not in result


def test_read_file_does_not_truncate_below_limit(tmp_path, edit_simulator):
    # Arrange
    max_lines = 10
    adapter = LocalFileSystemAdapter(
        edit_simulator=edit_simulator, root_dir=str(tmp_path), max_read_lines=max_lines
    )

    file_path = tmp_path / "small_file.txt"
    content = "line1\nline2"
    file_path.write_text(content, encoding="utf-8")

    # Act
    result = adapter.read_file("small_file.txt")

    # Assert
    assert result == content


def test_read_files_in_vault_returns_full_content_beyond_max_lines(
    tmp_path, edit_simulator
):
    """
    Scenario: Context-embedded files bypass the READ cap.

    Given a file with more lines than read.max_lines,
    When it is read during context assembly (read_files_in_vault),
    Then the full, untruncated content is returned,
    And the READ *action* cap on read_file remains unchanged.
    """
    # Arrange: a file whose line count exceeds the READ cap.
    max_lines = 3
    adapter = LocalFileSystemAdapter(
        edit_simulator=edit_simulator, root_dir=str(tmp_path), max_read_lines=max_lines
    )
    content = "line1\nline2\nline3\nline4\nline5"
    (tmp_path / "long_report.md").write_text(content, encoding="utf-8")

    # Act: context assembly reads the file.
    result = adapter.read_files_in_vault(["long_report.md"])

    # Assert: verbatim content, no truncation hint applied.
    assert result["long_report.md"] == content
