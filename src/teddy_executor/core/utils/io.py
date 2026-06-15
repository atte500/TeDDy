import logging
import re
import sys
from typing import Optional, TextIO


class _TeeWriter:
    def __init__(self, original: TextIO, log_file: TextIO):
        self._original = original
        self._log_file = log_file

    # ANSI escape sequence pattern (e.g., \x1b[31m, \x1b[1;33m, \x1b[A)
    _ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

    def write(self, text: str) -> None:
        # Terminal always gets raw text (colours preserved)
        self._original.write(text)
        self._original.flush()
        # Log file gets cleaned text (ANSI stripped)
        clean = self._ANSI_ESCAPE.sub("", text)
        self._log_file.write(clean)
        self._log_file.flush()

    def flush(self) -> None:
        self._original.flush()
        try:
            self._log_file.flush()
        except OSError:
            pass

    def isatty(self) -> bool:
        return self._original.isatty()

    @property
    def encoding(self) -> str:
        return self._original.encoding or "utf-8"


class Tee:
    def __init__(self, log_file: TextIO):
        self._log_file: Optional[TextIO] = log_file
        self._original_stdout: Optional[TextIO] = None
        self._original_stderr: Optional[TextIO] = None

    def __enter__(self) -> "Tee":
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        if self._log_file is None:
            return self
        sys.stdout = _TeeWriter(self._original_stdout, self._log_file)
        sys.stderr = _TeeWriter(self._original_stderr, self._log_file)

        # Fix for bug 22: Replace root logger handlers with new ones that use
        # the current sys.stderr (the Tee proxy). This robustly ensures logging
        # output flows through the Tee, regardless of how handlers were added.
        old_handlers = list(logging.root.handlers)
        for h in old_handlers:
            logging.root.removeHandler(h)
            h.close()
        new_handler = logging.StreamHandler(sys.stderr)
        new_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.root.addHandler(new_handler)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
        if self._original_stderr is not None:
            sys.stderr = self._original_stderr
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
