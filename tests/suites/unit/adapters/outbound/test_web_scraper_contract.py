from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.core.ports.outbound.web_scraper import WebScraper

from unittest.mock import patch, Mock


def test_web_scraper_contract_accepts_extraction_hints():
    """
    The WebScraper port and adapter should accept optional extraction hints
    to allow the caller (e.g., ContextService) to request specific parsing behavior.
    """
    scraper: WebScraper = WebScraperAdapter()

    # Mocking requests.get to ensure we don't hit the network and
    # focusing only on the signature validation.
    with patch("requests.get") as mock_get:
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.status_code = 200

        # This should NOT raise a TypeError now
        scraper.get_content("https://example.com", include_comments=True)


def test_web_scraper_contract_is_implemented_by_adapter():
    """Verification that the adapter still satisfies the Protocol."""
    scraper: WebScraper = WebScraperAdapter()
    assert isinstance(scraper, WebScraper)


def test_web_scraper_disables_high_recall_flags_and_truncates_lines():
    # Arrange
    mock_config = Mock()
    # Set the max_lines to 3 for testing
    mock_config.get_setting.return_value = 3

    adapter = WebScraperAdapter(config_service=mock_config)

    # Mock trafilatura and the internal rotation fetcher
    mock_trafilatura = Mock()
    # Generate 5 lines of markdown
    mock_trafilatura.extract.return_value = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    adapter._get_trafilatura = Mock(return_value=mock_trafilatura)
    adapter._fetch_with_rotation = Mock(return_value="<html>Dummy</html>")

    # Act
    result = adapter.get_content("http://example.com")

    # Assert
    # 1. Verify the correct flags were passed
    mock_trafilatura.extract.assert_called_once_with(
        "<html>Dummy</html>",
        output_format="markdown",
        include_links=True,
        include_formatting=True,
        favor_recall=False,  # Must be False
        include_comments=False,  # Must be False
        include_tables=True,
    )

    # 2. Verify truncation (head of the document up to max_lines)
    assert result == "Line 1\nLine 2\nLine 3"
