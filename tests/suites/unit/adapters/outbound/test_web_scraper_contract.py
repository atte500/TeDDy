from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.core.ports.outbound.web_scraper import WebScraper

from unittest.mock import patch


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
