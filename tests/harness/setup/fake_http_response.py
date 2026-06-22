"""FakeHTTPResponse: A test helper to simulate urllib HTTP responses."""

from __future__ import annotations

from typing import Any


class FakeHTTPResponse:
    """Simulates a urllib.response.addinfourl response for testing.

    Usage:
        response = FakeHTTPResponse(data='{"key": "value"}', status_code=200)
        body = response.read().decode("utf-8")
        code = response.getcode()
    """

    def __init__(self, data: str, status_code: int = 200) -> None:
        self._data = data.encode("utf-8")
        self._status_code = status_code
        self.headers: dict[str, Any] = {}

    def read(self) -> bytes:
        """Return the response body as bytes."""
        return self._data

    def getcode(self) -> int:
        """Return the HTTP status code."""
        return self._status_code

    def __enter__(self) -> FakeHTTPResponse:
        """Support context manager protocol (like urllib.request.urlopen)."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager (no-op for test helper)."""
        pass
