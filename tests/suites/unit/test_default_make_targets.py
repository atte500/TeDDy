"""Tests for the shipped Makefile and template lockstep."""

from __future__ import annotations

import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _PROJECT_ROOT / "Makefile"
_PROJECT_TEMPLATE = _PROJECT_ROOT / "docs" / "templates" / "makefile.md"
_BUNDLED_TEMPLATE = (
    _PROJECT_ROOT / "src" / "teddy_executor" / "resources" / "templates" / "makefile.md"
)


def test_makefile_stays_ascii_only() -> None:
    """Makefile text must stay ASCII so Windows consoles do not mojibake it."""
    text = _MAKEFILE.read_bytes()
    assert text.isascii(), "Makefile text must stay ASCII"


def test_template_copies_are_byte_identical() -> None:
    """Ensures documentation template and bundled resource template stay in lockstep."""
    assert _PROJECT_TEMPLATE.read_bytes() == _BUNDLED_TEMPLATE.read_bytes()


def test_make_help_executes_successfully() -> None:
    """Validates that running make help parses fragments and prints targets cleanly."""
    result = subprocess.run(
        ["make", "help"],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Available Makefile targets:" in result.stdout
