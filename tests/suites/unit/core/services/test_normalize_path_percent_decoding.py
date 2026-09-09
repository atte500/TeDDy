"""
Regression test for percent-encoded file paths (%20 to space, etc.).

Verifies that `normalize_path` in parser_infrastructure decodes
percent-encoded sequences (e.g., `%20` to space).
"""

from __future__ import annotations

import pytest

from teddy_executor.core.services.parser_infrastructure import normalize_path


# Test cases for URL-like paths that should preserve percent-encoding
_URL_PATHS_PRESERVE = [
    (
        "http://example.com/path%20with%20spaces",
        "http://example.com/path%20with%20spaces",
    ),
    ("https://example.com/file%20name.txt", "https://example.com/file%20name.txt"),
    ("http://example.com/doc%23section", "http://example.com/doc%23section"),
    ("http://example.com/api%2Fv1/resource", "http://example.com/api%2Fv1/resource"),
    ("ftp://files.example.com/doc%20v2.txt", "ftp://files.example.com/doc%20v2.txt"),
    ("file:///local/path%20name.txt", "file:///local/path%20name.txt"),
    ("www.example.com/path%20with%20spaces", "www.example.com/path%20with%20spaces"),
    ("www.example.com/file%20name.txt", "www.example.com/file%20name.txt"),
    ("www.example.com/doc%23section", "www.example.com/doc%23section"),
    ("www.example.com/api%2Fv1/resource", "www.example.com/api%2Fv1/resource"),
    (
        "www.my-site.co.uk/path%20with%20spaces",
        "www.my-site.co.uk/path%20with%20spaces",
    ),
]

# Test cases for non-URL paths that should decode percent-encoding
_PATH_PATHS_DECODE = [
    ("hello%20world.txt", "hello world.txt"),
    ("a%20b%20c.txt", "a b c.txt"),
    ("folder\\sub%20dir\\file.txt", "folder/sub dir/file.txt"),
    ("normal/path.txt", "normal/path.txt"),
    ("folder\\file.txt", "folder/file.txt"),
    ("www.txt", "www.txt"),  # bare "www.txt" is a file, not a URL
    ("www.something", "www.something"),  # www. with no TLD is ambiguous, treat as path
]


class TestNormalizePathDecoding:
    """Unit tests for the normalize_path function."""

    @pytest.mark.parametrize("input_path,expected", _URL_PATHS_PRESERVE)
    def test_url_paths_preserve_percent_encoding(self, input_path: str, expected: str):
        """URL-like paths preserve percent-encoded sequences."""
        result = normalize_path(input_path)
        assert result == expected, f"Expected {expected!r}, got {result!r}"

    @pytest.mark.parametrize("input_path,expected", _PATH_PATHS_DECODE)
    def test_file_paths_decode_percent_encoding(self, input_path: str, expected: str):
        """Regular file paths decode percent-encoded sequences."""
        result = normalize_path(input_path)
        assert result == expected, f"Expected {expected!r}, got {result!r}"

    def test_backslash_conversion_and_url_preserve(self):
        """Backslash conversion still works and doesn't affect URL detection."""
        # Backslashes in URLs shouldn't happen, but if they do, they're converted
        # before URL detection runs (the replace is first).
        result = normalize_path("http://example.com\\path%20name")
        # Backslash gets converted to /, then URL detection triggers
        assert result == "http://example.com/path%20name", f"Unexpected: {result!r}"

    def test_backslash_conversion_and_url_preserve_www(self):
        """Backslash conversion preserves bare www. URLs too."""
        result = normalize_path("www.example.com\\path%20name")
        # Backslash gets converted to /, then bare URL detection triggers
        assert result == "www.example.com/path%20name", f"Unexpected: {result!r}"
