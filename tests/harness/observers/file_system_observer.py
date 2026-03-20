import re
from pathlib import Path
from typing import List


class FileSystemObserver:
    """
    Observer component for performing assertions against the local file system.
    """

    def assert_file_exists(self, path: Path) -> None:
        """Raises AssertionError if the file is missing."""
        if not path.exists():
            raise AssertionError(f"File {path.name} does not exist at {path}")

    def assert_file_content_equals(self, path: Path, expected: str) -> None:
        """Verifies exact content matching."""
        self.assert_file_exists(path)
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise AssertionError(
                f"File {path.name} content mismatch.\nExpected: {expected!r}\nActual: {actual!r}"
            )

    def assert_directory_contains(self, root: Path, expected_files: List[str]) -> None:
        """Verifies that a directory contains exactly the specified relative paths."""
        actual_files = sorted(
            [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
        )
        expected_sorted = sorted(expected_files)
        if actual_files != expected_sorted:
            raise AssertionError(
                f"Directory content mismatch.\nExpected: {expected_sorted}\nActual: {actual_files}"
            )

    def assert_file_matches_pattern(self, path: Path, pattern: str) -> None:
        """Verifies content against a regex."""
        self.assert_file_exists(path)
        actual = path.read_text(encoding="utf-8")
        if not re.search(pattern, actual):
            raise AssertionError(
                f"File {path.name} does not match pattern: {pattern!r}\nContent: {actual!r}"
            )
