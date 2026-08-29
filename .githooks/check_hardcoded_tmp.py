#!/usr/bin/env python3
"""Pre-commit hook: No Hardcoded /tmp/ Paths in Test Files.

Checks staged test files (ACM = Added/Copied/Modified) for hardcoded
POSIX /tmp/ paths that would break on Windows. Exits with 1 if any
violation is found.
"""

import subprocess  # nosec B404
import sys


def _get_staged_test_files() -> list[str]:
    """Return list of staged test files (Added, Copied, Modified)."""
    result = subprocess.run(  # nosec B603 B607
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        print("ERROR: git diff --cached failed")
        sys.exit(1)
    staged = result.stdout.strip().splitlines()
    return [f for f in staged if f.startswith("tests/")]


def _starts_triple_quote(line: str) -> bool:
    """Check if line starts a triple-quoted string (single or multiline)."""
    stripped = line.strip()
    return stripped.startswith('"""') or stripped.startswith("'''")


def _contains_triple_quote(line: str) -> bool:
    """Check if line contains a triple-quote sequence."""
    return '"""' in line or "'''" in line


def _is_harmless_tmp_reference(line: str) -> bool:
    """Return True if /tmp/ in this line is only a harmless reference within
    a comment or string literal, not actual executable code."""
    stripped = line.strip()
    # Skip single-line comments
    if stripped.startswith("#") or stripped.startswith("//"):
        return True
    # Skip lines where /tmp/ is inside a string literal or RST code block
    idx = stripped.find("/tmp/")  # nosec B108
    if idx > 0 and idx + 5 < len(stripped):
        before = stripped[idx - 1]
        after = stripped[idx + 5]
        if before == after and before in "'\"`":
            return True
    return False


def main() -> int:
    """Check all staged test files for hardcoded /tmp/ paths."""
    test_files = _get_staged_test_files()
    found_violations = False
    in_multiline = False

    for filepath in test_files:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()

                # Track and skip multiline string bodies
                if not in_multiline:
                    if _starts_triple_quote(line):
                        if not _contains_triple_quote(line):
                            in_multiline = True
                        continue
                else:
                    if _contains_triple_quote(line):
                        in_multiline = False
                    continue

                if "/tmp/" not in line:  # nosec B108
                    continue

                if _is_harmless_tmp_reference(line):
                    continue

                print(
                    f"ERROR: Hardcoded POSIX /tmp/ path found in {filepath}:{line_num}"
                )
                print("  Use temp_path fixture or tempfile.gettempdir() instead.")
                print(f"  Line content: {line.rstrip()}")
                found_violations = True

    return 1 if found_violations else 0


if __name__ == "__main__":
    sys.exit(main())
