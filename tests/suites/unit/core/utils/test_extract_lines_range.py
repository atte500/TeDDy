"""Unit tests for the extract_lines_range utility function."""

from teddy_executor.core.utils.string import extract_lines_range


def test_extract_lines_range_standard_range():
    """Lines: 10-20 extracts lines 10 through 20 inclusive."""
    content = "\n".join(f"Line {i}" for i in range(1, 31))
    result = extract_lines_range(content, "10-20")
    expected = "\n".join(f"Line {i}" for i in range(10, 21))
    assert result == expected


def test_extract_lines_range_first_20():
    """Lines: -20 extracts first 20 lines."""
    content = "\n".join(f"Line {i}" for i in range(1, 31))
    result = extract_lines_range(content, "-20")
    expected = "\n".join(f"Line {i}" for i in range(1, 21))
    assert result == expected


def test_extract_lines_range_from_25_to_end():
    """Lines: 25- extracts from line 25 to end."""
    content = "\n".join(f"Line {i}" for i in range(1, 31))
    result = extract_lines_range(content, "25-")
    expected = "\n".join(f"Line {i}" for i in range(25, 31))
    assert result == expected


def test_extract_lines_range_single_line():
    """Lines: 5 extracts only line 5."""
    content = "\n".join(f"Line {i}" for i in range(1, 11))
    result = extract_lines_range(content, "5")
    assert result == "Line 5"


def test_extract_lines_range_malformed_returns_full():
    """Invalid lines spec falls back to full content."""
    content = "line1\nline2\nline3"
    result = extract_lines_range(content, "abc")
    assert result == content


def test_extract_lines_range_start_gt_total_returns_empty():
    """Start beyond file length returns empty string."""
    content = "line1\nline2"
    result = extract_lines_range(content, "100-200")
    assert result == ""


def test_extract_lines_range_empty_content():
    """Empty content returns empty string regardless of spec."""
    assert extract_lines_range("", "1-10") == ""
