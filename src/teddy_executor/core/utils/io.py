"""I/O utility classes for the TeDDy execution environment."""

import logging
import sys
from pathlib import Path
from typing import TextIO

logger = logging.getLogger(__name__)


class _TeeWriter:
    """A proxy writer that forwards write/flush/isatty to two output streams."""

    def __init__(self, original: TextIO, log_file: TextIO) -> None:
        self._original = original
        self._log_file = log_file

    def write(self, text: str) -> None:
        """Write text to both original stdout and the log file."""
        self._original.write(text)
        self._original.flush()
        self._log_file.write(text)
        self._log_file.flush()

    def flush(self) -> None:
        """Flush both output streams."""
        self._original.flush()
        self._log_file.flush()

    def isatty(self) -> bool:
        """Forward isatty to the original stdout."""
        return self._original.isatty()


class Tee:
    """
    A context manager that duplicates sys.stdout writes to both the original
    stdout and a log file.

    This is used to produce the session history.log by tee'ing console output
    that is already being printed during SessionOrchestrator execution.
    """

    def __init__(self, log_path: Path) -> None:
        """Initialize the Tee with a path to the log file.

        Args:
            log_path: The filesystem path where output will be appended.
        """
        self._log_path = log_path
        self._original_stdout: TextIO | None = None
        self._log_file: TextIO | None = None
        self._writer: _TeeWriter | None = None

    def __enter__(self) -> "Tee":
        """Install the Tee by replacing sys.stdout with the proxy writer."""
        self._original_stdout = sys.stdout
        try:
            self._log_file = open(self._log_path, "a", encoding="utf-8")  # noqa: SIM115
        except OSError as e:
            logger.debug("Failed to open history.log for tee: %s", e)
            return self  # Skip tee, return without modifying sys.stdout

        self._writer = _TeeWriter(self._original_stdout, self._log_file)
        sys.stdout = self._writer  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Restore the original sys.stdout and close the log file."""
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout

        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError as e:
                logger.debug("Failed to close history.log: %s", e)
