import requests
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter


class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise requests.exceptions.HTTPError(
                f"Error {self.status_code}", response=self
            )


def test_get_content_handles_403_with_fallback(monkeypatch):
    """
    Desired behavior: If requests.get returns 403, we should fallback to trafilatura.fetch_url.
    This test currently fails with HTTPError.
    """
    # Arrange
    adapter = WebScraperAdapter()
    url = "https://www.pnas.org/doi/10.1073/pnas.2416294121"

    def mock_get(url, **kwargs):
        return MockResponse("Forbidden", 403)

    import trafilatura

    def mock_fetch(url):
        return "<html><body>Fallback Content</body></html>"

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(trafilatura, "fetch_url", mock_fetch)

    # Act
    content = adapter.get_content(url)

    # Assert
    assert "Fallback Content" in content


def test_get_content_raw_github_returns_content(monkeypatch):
    """
    Desired behavior: raw.githubusercontent.com should return verbatim content.
    This test currently fails with an empty string return.
    """
    # Arrange
    adapter = WebScraperAdapter()
    url = "https://raw.githubusercontent.com/user/repo/main/README.md"
    raw_content = "# README\nThis is raw content."

    def mock_get(url, **kwargs):
        return MockResponse(raw_content, 200)

    monkeypatch.setattr(requests, "get", mock_get)

    # Act
    content = adapter.get_content(url)

    # Assert
    assert content == raw_content


# -------------------- Regression: Logging Suppression (Bug 39, Point 3) --------------------


def test_get_content_suppresses_trafilatura_logging_on_403(monkeypatch, capsys):
    """Regression test for Bug 39 — trafilatura logging suppression.

    Given a URL that returns 403
    When get_content is called
    Then no trafilatura "not a 200 response" message should appear on stderr.

    Note: This test may not reproduce stderr in all environments (trafilatura
    logger may have NullHandler locally). It asserts that the fix does not
    introduce new stderr output and that the call completes without error.
    """
    adapter = WebScraperAdapter()
    url = "https://httpbin.org/status/403"

    adapter.get_content(url)

    captured = capsys.readouterr()
    err = captured.err

    # Assert: no trafilatura logging leaked to stderr.
    # If the local environment suppresses trafilatura logging, this is a no-op.
    # In CI/scrape.py, this would catch the bug.
    assert "not a 200 response" not in err, (
        f"BUG: trafilatura logging leaked to stderr: {err[:200]}"
    )
