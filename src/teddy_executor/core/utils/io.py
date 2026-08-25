import logging
import re
import sys
from typing import Optional, TextIO


class _TeeWriter:
    def __init__(self, original: TextIO, log_file: TextIO):
        self._original = original
        self._log_file = log_file
        self._log_file_closed = False  # Track closure state

    # Comprehensive ANSI escape sequence pattern.
    # Matches all CSI sequences (including private modes like \x1b[?12l),
    # OSC sequences (e.g., \x1b]0;title\x07), DCS/SOS/PM/APC, and SS2/SS3/ST.
    _ANSI_ESCAPE = re.compile(
        r"\x1b\[[0-?]*[ -/]*[@-~]"  # CSI sequences (all variants)
        r"|\x1b\].*?(\x1b\\|\x07)"  # OSC sequences
        r"|\x1b[PX^_].*?\x1b\\"  # DCS, SOS, PM, APC
        r"|\x1b[NO\\]"  # SS2, SS3, ST
    )

    def write(self, text: str) -> None:
        # Terminal always gets raw text (colours preserved)
        self._original.write(text)
        self._original.flush()
        # Log file gets cleaned text (ANSI stripped)
        clean = self._ANSI_ESCAPE.sub("", text)
        if not self._log_file_closed:
            try:
                self._log_file.write(clean)
                self._log_file.flush()
            except (ValueError, OSError):
                self._log_file_closed = True

    def flush(self) -> None:
        self._original.flush()
        if not self._log_file_closed:
            try:
                self._log_file.flush()
            except (ValueError, OSError):
                self._log_file_closed = True

    def isatty(self) -> bool:
        return self._original.isatty()

    def fileno(self) -> int:
        """Delegate fileno to the original stream.

        This is required because Python's TextIO protocol includes fileno()
        as an expected method. Without it, any code that inspects the stream's
        file descriptor (e.g., terminal capability checks via os.isatty(fd),
        or libraries like prompt_toolkit) will crash with AttributeError.
        """
        return self._original.fileno()

    @property
    def encoding(self) -> str:
        return self._original.encoding or "utf-8"


class Tee:
    def __init__(self, log_file: Optional[TextIO]):
        self._log_file: Optional[TextIO] = log_file
        self._original_stdout: Optional[TextIO] = None
        self._original_stderr: Optional[TextIO] = None
        self._saved_handlers: list[logging.Handler] = []
        self._tee_handler: Optional[logging.StreamHandler] = None

    def __enter__(self) -> "Tee":
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        if self._log_file is None:
            return self
        sys.stdout = _TeeWriter(self._original_stdout, self._log_file)
        sys.stderr = _TeeWriter(self._original_stderr, self._log_file)

        # Replace root logger handlers with new ones that use the current
        # sys.stderr (the Tee proxy). Save original handlers WITHOUT closing
        # them so they can be restored in __exit__.
        self._saved_handlers = list(logging.root.handlers)
        for h in self._saved_handlers:
            logging.root.removeHandler(h)
        self._tee_handler = logging.StreamHandler(sys.stderr)
        self._tee_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.root.addHandler(self._tee_handler)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Remove the Tee handler by instance identity
        if self._tee_handler is not None:
            logging.root.removeHandler(self._tee_handler)
            self._tee_handler = None

        # Restore saved handlers
        for h in self._saved_handlers:
            logging.root.addHandler(h)

        # Restore original streams
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
        if self._original_stderr is not None:
            sys.stderr = self._original_stderr
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
        self._saved_handlers = []
