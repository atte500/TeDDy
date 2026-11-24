"""In-memory fake for the IPdfExtractor outbound port."""

from __future__ import annotations


class FakePdfExtractor:
    """Deterministic IPdfExtractor double for harness-driven wiring tests.

    Returns a fixed text layer and records every ``extract_text`` call, so a
    test can assert both the extracted result and the exact bytes/source that
    reached the port without invoking pypdf.
    """

    def __init__(self, text: str = "extracted pdf text") -> None:
        self._text = text
        self.calls: list[tuple[bytes, str]] = []

    def extract_text(self, data: bytes, source: str) -> str:
        self.calls.append((data, source))
        return self._text
