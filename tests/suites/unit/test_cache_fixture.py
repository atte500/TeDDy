"""Tests for the temp cache directory fixture."""

from pathlib import Path


def test_temp_cache_dir_is_writable_path(temp_cache_dir):
    """The temp_cache_dir fixture should provide a writable Path."""
    assert isinstance(temp_cache_dir, Path), (
        f"Expected Path, got {type(temp_cache_dir)}"
    )
    assert temp_cache_dir.is_dir(), "Path must be an existing directory"
    # Verify the directory is writable
    test_file = temp_cache_dir / "test_write.txt"
    test_file.write_text("hello", encoding="utf-8")
    assert test_file.read_text(encoding="utf-8") == "hello"


def test_temp_cache_dir_isolated_between_calls(temp_cache_dir):
    """Each call to the fixture should provide a clean, isolated directory."""
    assert isinstance(temp_cache_dir, Path)
    # The directory should be empty initially
    contents = list(temp_cache_dir.iterdir())
    assert contents == [], f"Expected empty directory, got {contents}"
    # Create a file to verify isolation (next call won't have it)
    marker = temp_cache_dir / ".marker"
    marker.write_text("exists", encoding="utf-8")
    assert marker.exists()
