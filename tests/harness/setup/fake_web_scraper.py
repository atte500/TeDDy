"""In-memory fake for the ``IWebScraper`` outbound port.

Mirrors ``fake_pdf_extractor``: a small hand-written double that returns scripted
bodies and records every call, so wiring, core, and adapter tests can drive the
cache-hit, cache-miss, and fetch-failure branches deterministically without
network access.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


class FakeWebScraper:
    """Deterministic ``IWebScraper`` double for harness-driven tests.

    Scripts one body per URL and one exception per URL, and records every
    ``get_content`` call as ``(url, truncate, kwargs)`` so a test can prove the
    coordinator never asks the scraper to truncate. An unscripted URL fails
    loudly, because a silently empty body would let a mis-scripted test pass.
    """

    def __init__(
        self,
        contents: Optional[Mapping[str, str]] = None,
        failures: Optional[Mapping[str, BaseException]] = None,
    ) -> None:
        self._contents: dict[str, str] = dict(contents or {})
        self._failures: dict[str, BaseException] = dict(failures or {})
        self.calls: list[tuple[str, bool, dict[str, Any]]] = []

    def get_content(self, url: str, truncate: bool = True, **kwargs: Any) -> str:
        self.calls.append((url, truncate, dict(kwargs)))
        if url in self._failures:
            raise self._failures[url]
        assert url in self._contents, f"FakeWebScraper received unscripted URL: {url}"
        return self._contents[url]
