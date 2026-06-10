import logging
import sys
from pathlib import Path
from typing import Optional, TextIO


class _TeeWriter:
    def __init__(self, original: TextIO, log_file: TextIO):
        self._original = original
        self._log_file = log_file

    def write(self, text: str) -> None:
        self._original.write(text)
        self._original.flush()
        self._log_file.write(text)
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
    def __init__(self, log_path: Path):
        self._log_path = log_path
        self._log_file: Optional[TextIO] = None
        self._original_stdout: Optional[TextIO] = None
        self._original_stderr: Optional[TextIO] = None

    def __enter__(self) -> "Tee":
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self._log_path, "a", encoding="utf-8")
        except OSError:
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
