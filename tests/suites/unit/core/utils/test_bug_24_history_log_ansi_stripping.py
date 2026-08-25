"""Regression test for Bug 24: History log contains ANSI escape codes.

Verifies that the Tee class strips ANSI escape sequences from the log file
while preserving them in the terminal output.
"""

import re
import sys
import tempfile
from pathlib import Path

# Add project src to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "src"))

from teddy_executor.core.utils.io import Tee

# Comprehensive ANSI pattern matching all escape sequence variants
_ANSI_PATTERN = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"  # CSI sequences (all variants)
    r"|\x1b\].*?(\x1b\\|\x07)"  # OSC sequences
    r"|\x1b[PX^_].*?\x1b\\"  # DCS, SOS, PM, APC
    r"|\x1b[NO\\]"  # SS2, SS3, ST
)


def test_ansi_codes_stripped_from_log():
    """Assert that ANSI escape codes do not appear in the log file after Tee capture."""
    log_path = Path(tempfile.mktemp(suffix=".log"))

    # Capture output containing ANSI codes via Tee
    log_file = open(log_path, "a", encoding="utf-8")
    with Tee(log_file):
        # These are typical ANSI sequences used by CLI formatter
        print("\x1b[31mRed text\x1b[0m")
        print("\x1b[1;33mYellow bold\x1b[0m")
        print("\x1b[?25hNormal text")  # cursor show (private mode)
        print("\x1b[?12lHidden cursor")  # DECRST private mode
        print("\x1b[?2004hBracketed paste")  # Bracketed paste mode

    log_content = log_path.read_text(encoding="utf-8")

    # Assert no ANSI escape sequences remain
    assert not _ANSI_PATTERN.search(log_content), (
        f"ANSI escape codes found in log content:\n{log_content!r}"
    )

    # Cleanup
    log_path.unlink(missing_ok=True)
