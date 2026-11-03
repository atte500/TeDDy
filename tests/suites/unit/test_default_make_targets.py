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
_PROBE_MK = _PROJECT_ROOT / "make" / "probe.mk"


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


def test_probe_recipe_clears_output_and_fails_loudly_on_download_failure() -> None:
    """The probe recipe must clear stale output before download and never suppress download errors."""
    lines = _PROBE_MK.read_text(encoding="utf-8").splitlines()
    clear_index = next(
        (
            i
            for i, line in enumerate(lines)
            if "rm -f spikes/debug/probe_output.txt" in line
        ),
        None,
    )
    download_index = next(
        (i for i, line in enumerate(lines) if "gh run download" in line),
        None,
    )
    assert clear_index is not None, (
        "probe recipe must clear spikes/debug/probe_output.txt"
    )
    assert download_index is not None, (
        "probe recipe must download the probe-result artifact"
    )
    assert clear_index < download_index, (
        "probe recipe must clear output before the download"
    )
    assert "|| true" not in lines[download_index], (
        "probe download must fail loudly, not be suppressed with || true"
    )
