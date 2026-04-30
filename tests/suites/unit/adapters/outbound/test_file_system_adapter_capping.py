import pytest
from unittest.mock import MagicMock
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)


@pytest.fixture
def edit_simulator():
    return MagicMock()


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
    expected_hint = "[Content truncated: Showing FIRST 3 of 5 lines. Use 'grep' or 'sed' via EXECUTE to read specific sections.]"
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
