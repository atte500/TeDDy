"""In-memory fake for the ``IWebContentCache`` outbound port.

Mirrors ``fake_pdf_extractor``: a small hand-written double that holds scripted
bodies and records every call, so wiring, core, and adapter tests can drive the
cached-hit, cache-miss, and tolerated-write-failure branches deterministically
without touching the filesystem.
"""

from __future__ import annotations

from typing import Mapping, Optional

from teddy_executor.core.domain.models.exceptions import WebContentCacheError


class FakeWebContentCache:
    """Deterministic ``IWebContentCache`` double for harness-driven tests.

    Holds a URL-keyed body map, records every load and merge, and mirrors the
    port's absent-session rule: a ``None`` session root reads as empty and
    accepts no merge. An optional scripted ``WebContentCacheError`` fails the
    merge before the map is touched, matching the adapter's promise that a
    failed write leaves the stored entries as they were.
    """

    def __init__(
        self,
        entries: Optional[Mapping[str, str]] = None,
        merge_error: Optional[WebContentCacheError] = None,
    ) -> None:
        self._entries: dict[str, str] = dict(entries or {})
        self._merge_error = merge_error
        self.load_calls: list[Optional[str]] = []
        self.merge_calls: list[tuple[Optional[str], dict[str, str]]] = []

    def load_entries(self, session_root: Optional[str]) -> dict[str, str]:
        self.load_calls.append(session_root)
        if session_root is None:
            return {}
        return dict(self._entries)

    def merge_entries(
        self, session_root: Optional[str], entries: Mapping[str, str]
    ) -> None:
        self.merge_calls.append((session_root, dict(entries)))
        if self._merge_error is not None:
            raise self._merge_error
        if session_root is None:
            return
        self._entries.update(entries)
