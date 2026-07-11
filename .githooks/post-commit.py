#!/usr/bin/env python3
"""
Post-commit hook: Mandatory full test suite gate.

Runs after every ``git commit``. If tests fail, the commit is reverted
while preserving all staged changes. This hook is NOT affected by
``--no-verify``, making it the only truly unskippable test gate.

Compatible with Windows and UNIX.
Dependencies: poetry run pytest (project's test runner)
"""

import subprocess
import sys


def _fail(message: str, detail: str | None = None) -> None:
    """Print a formatted error message and revert the commit."""
    print()
    print("=" * 44)
    print(f" {message}")
    print("=" * 44)
    if detail:
        print(detail)
    print()
    print("The commit has been undone. Fix the issue and re-commit.")
    print("=" * 44)
    print()
    subprocess.run(["git", "reset", "--soft", "HEAD~1"], check=True)
    sys.exit(1)


def main() -> None:
    # Pre-flight: ensure poetry is installed
    try:
        subprocess.run(
            ["poetry", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        _fail(
            "ERROR: poetry is not installed",
            "Install poetry to run the test suite.\n"
            "  curl -sSL https://install.python-poetry.org | python3 -",
        )

    # Pre-flight: ensure pytest is available in the poetry environment
    result = subprocess.run(
        ["poetry", "run", "python", "-c", "import pytest"],
        capture_output=True,
    )
    if result.returncode != 0:
        _fail(
            "ERROR: pytest is not installed",
            "Run 'poetry install --with dev' to install test dependencies.",
        )

    # Run the full test suite (capture exit code; do not use check=True)
    result = subprocess.run(
        ["poetry", "run", "pytest", "--tb=short", "-q"],
    )

    if result.returncode != 0:
        _fail("TESTS FAILED \u2014 Reverting commit")


if __name__ == "__main__":
    main()