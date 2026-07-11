#!/usr/bin/env python3
"""
Pre-commit hook: Enforce explicit encoding='utf-8' in file operations.

Scans each Python file for:
  - .read_text() or .write_text() called without encoding= parameter.
  - open(..., '<text_mode>') where mode is text-based (no 'b') and encoding= is missing.

Exits with 1 if any violations found. Uses simple string operations for speed.
"""

import sys


def _is_text_mode(mode_str: str) -> bool:
    """Return True if the mode string represents a text mode (no 'b')."""
    return bool(mode_str and any(c in mode_str for c in "wrax") and "b" not in mode_str)


def _find_text_mode(rest: str) -> str | None:
    """Extract text-mode string from the content after 'open('.

    Returns the mode string (e.g., 'w', 'r+') if it's a text mode,
    or None if no text mode found.
    """
    in_quote = False
    quote_char: str | None = None
    mode_str = ""
    for ch in rest:
        if not in_quote and ch in ("'", '"'):
            in_quote = True
            quote_char = ch
            mode_str = ""
        elif in_quote:
            if ch == quote_char:
                if _is_text_mode(mode_str):
                    return mode_str
                in_quote = False
            else:
                mode_str += ch
    return None


def _check_read_write_text(line: str, filepath: str, lineno: int) -> str | None:
    """Check if .read_text() or .write_text() is missing encoding.

    Returns an error message string, or None if compliant.
    """
    if ".read_text()" in line or ".write_text()" in line:
        if "encoding=" not in line:
            return (
                f'UTF-8 Compliance Violation: Missing explicit encoding="utf-8" in '
                f"{filepath}:{lineno}\n"
                f"  {line}"
            )
    return None


def _check_open_encoding(line: str, filepath: str, lineno: int) -> str | None:
    """Check if open() with text mode is missing encoding.

    Returns an error message string, or None if compliant.
    """
    if "open(" not in line or "encoding=" in line:
        return None
    paren = line.find("open(")
    rest = line[paren + 5 :]
    mode = _find_text_mode(rest)
    if mode is not None:
        return (
            f'UTF-8 Compliance Violation: Missing explicit encoding="utf-8" in '
            f"{filepath}:{lineno}\n"
            f"  {line}"
        )
    return None


def check_file(filepath: str) -> list[str]:
    """Check a single file for violations. Returns list of error messages."""
    violations: list[str] = []
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        return [f"Error reading {filepath}: {e}"]

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue
        # Check read_text/write_text missing encoding
        error = _check_read_write_text(stripped, filepath, lineno)
        if error is not None:
            violations.append(error)
            continue
        # Check open() with text mode missing encoding
        error = _check_open_encoding(stripped, filepath, lineno)
        if error is not None:
            violations.append(error)

    return violations


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0

    exit_code = 0
    for filepath in files:
        normalized = filepath.replace("\\", "/")
        if not normalized.startswith("src/"):
            continue
        violations = check_file(filepath)
        if violations:
            for msg in violations:
                print(msg)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
