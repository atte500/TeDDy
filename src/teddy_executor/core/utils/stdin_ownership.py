"""Process-global stdin-ownership guard (Bug 56 bare-`q`).

Some interactive prompts (the console ask loop, the external editor) read
directly from ``stdin``. The terminal quit-key reader must not consume bytes
while another reader owns stdin, so it consults this process-global guard and
backs off while ownership is claimed.

This mirrors the accepted process-global treatment of the signal-disposition
(``InterruptGuard``) and terminal-mode (``restore_cooked_mode``) concerns; the
module is stdlib-only and imports no DI framework.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_lock = threading.Lock()
_ownership_depth = 0


@contextmanager
def stdin_owned() -> Iterator[None]:
    """Claim stdin for the duration of the block.

    Ownership is reference-counted so nested claims behave correctly, and is
    always released on exit -- including when the block raises.
    """
    global _ownership_depth
    with _lock:
        _ownership_depth += 1
    try:
        yield
    finally:
        with _lock:
            _ownership_depth -= 1


def is_stdin_owned() -> bool:
    """Return True while any reader currently owns stdin."""
    with _lock:
        return _ownership_depth > 0
