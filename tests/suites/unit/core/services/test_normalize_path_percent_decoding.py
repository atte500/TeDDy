"""
Regression test for percent-encoded file paths (%20 to space, etc.).

Verifies that `normalize_path` in parser_infrastructure decodes
percent-encoded sequences (e.g., `%20` to space).
"""

from __future__ import annotations

from teddy_executor.core.services.parser_infrastructure import normalize_path


class TestNormalizePathDecoding:
    """Unit tests for the normalize_path function."""

    def test_simple_percent20_to_space(self):
        """Single %20 decodes to a space."""
        result = normalize_path("hello%20world.txt")
        assert "%20" not in result, f"Decode failed: {result!r}"
        assert result == "hello world.txt", f"Unexpected: {result!r}"

    def test_multiple_percent20(self):
        """Multiple %20 sequences decoded."""
        result = normalize_path("a%20b%20c.txt")
        assert "%20" not in result, f"Decode failed: {result!r}"
        assert result == "a b c.txt", f"Unexpected: {result!r}"

    def test_backslash_conversion_preserved(self):
        """Existing backslash to forward-slash conversion still works."""
        result = normalize_path("folder\\file.txt")
        assert result == "folder/file.txt", f"Expected forward slash, got: {result!r}"

    def test_no_percent_encoding_preserved(self):
        """Normal paths without encoding are unchanged."""
        result = normalize_path("normal/path.txt")
        assert result == "normal/path.txt", f"Unexpected: {result!r}"

    def test_mixed_backslash_and_percent20(self):
        """Both backslash conversion and percent decoding work together."""
        result = normalize_path("folder\\sub%20dir\\file.txt")
        assert result == "folder/sub dir/file.txt", f"Unexpected: {result!r}"
        assert "%20" not in result, f"Decode failed: {result!r}"

    def test_url_http_preserves_percent20(self):
        """HTTP URLs with %20 are not decoded (structural URL encoding)."""
        result = normalize_path("http://example.com/path%20with%20spaces")
        assert result == "http://example.com/path%20with%20spaces", (
            f"URL decoded: {result!r}"
        )

    def test_url_https_preserves_percent20(self):
        """HTTPS URLs with %20 are not decoded."""
        result = normalize_path("https://example.com/file%20name.txt")
        assert result == "https://example.com/file%20name.txt", (
            f"URL decoded: {result!r}"
        )

    def test_url_preserves_percent23(self):
        """URLs with %23 (#) are preserved (fragment identifier encoding)."""
        result = normalize_path("http://example.com/doc%23section")
        assert result == "http://example.com/doc%23section", f"URL decoded: {result!r}"

    def test_url_preserves_percent2F(self):
        """URLs with %2F (/) are preserved (path segment encoding)."""
        result = normalize_path("http://example.com/api%2Fv1/resource")
        assert result == "http://example.com/api%2Fv1/resource", (
            f"URL decoded: {result!r}"
        )
