"""Thread-safe, counted suppression of logging below CRITICAL.

`logging.disable()` mutates a single PROCESS-GLOBAL logging threshold with
no thread affinity. A bare enter/restore toggle is racy under concurrent
callers: the first caller to exit restores the threshold while a sibling is
still inside a noisy third-party call, letting its WARNINGs escape to any
configured handler (empirically proven for WebScraperAdapter under
ContextService's parallel URL fetching).

This context manager replaces the bare toggle with a reference count guarded
by a lock: only the FIRST entrant closes the threshold and only the LAST
exiter re-opens it, so the threshold stays closed until every concurrent
user has exited its scope.
"""

import logging
import threading


_SUPPRESSION_LOCK = threading.Lock()
_SUPPRESSION_DEPTH = 0


class suppressed_logging:
    """Counted suppression scope: logging below CRITICAL while any user is inside."""

    def __enter__(self) -> None:
        global _SUPPRESSION_DEPTH
        with _SUPPRESSION_LOCK:
            _SUPPRESSION_DEPTH += 1
            if _SUPPRESSION_DEPTH == 1:
                logging.disable(logging.CRITICAL)

    def __exit__(self, exc_type, exc, tb) -> None:
        global _SUPPRESSION_DEPTH
        with _SUPPRESSION_LOCK:
            _SUPPRESSION_DEPTH -= 1
            if _SUPPRESSION_DEPTH == 0:
                logging.disable(logging.NOTSET)
