"""
Regression test for bug 22: history.log missing action logs.

The bug: logging.StreamHandler caches original sys.stderr at module import
time and continues writing to it after Tee replaces sys.stderr, bypassing
the Tee proxy. This test verifies that logger.info() output via the root
logger is captured in the Tee log file after Tee installation.
"""

import logging
import sys
import tempfile
from pathlib import Path

from teddy_executor.core.utils.io import Tee


def test_logging_output_captured_by_tee():
    """
    After Tee is installed, logger.info() messages logged to a child
    logger (propagating to root) MUST be written to the Tee log file.
    This reproduces bug 22 with the real logging setup.
    """
    # Create a temporary log file for the Tee
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        log_path = Path(tmp.name)

    # Save original root handlers to restore later
    original_handlers = logging.root.handlers[:]

    try:
        # Create a handler on the root logger (simulates __main__.py setup)
        root_handler = logging.StreamHandler(sys.stderr)
        root_handler.setLevel(logging.INFO)
        logging.root.addHandler(root_handler)
        logging.root.setLevel(logging.INFO)

        # Install Tee (simulates session execution)
        tee = Tee(log_path)
        tee.__enter__()

        # Log a message while Tee is active (the bug: originally bypasses Tee)
        # Use a child logger that propagates to root (like ActionDispatcher does)
        test_logger = logging.getLogger("teddy_executor.test")
        test_logger.info("BUG22_TEST_MESSAGE")

        # Restore streams
        tee.__exit__(None, None, None)

        # Read the log file
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # The logged message MUST be in the Tee log file
        assert "BUG22_TEST_MESSAGE" in content, (
            f"Logger output was NOT captured in Tee log file. "
            f"Log content: {repr(content)}"
        )

    finally:
        # Cleanup
        log_path.unlink(missing_ok=True)
        # Restore original root handlers
        logging.root.handlers = original_handlers
        root_handler.close()
