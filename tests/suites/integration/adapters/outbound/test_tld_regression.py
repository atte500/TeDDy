"""Regression test for Bug #03: tld import error.

Ensures the tld package and its get_tld function are importable,
which is required by the web scraper adapter's dependency chain.
"""


def test_tld_get_tld_importable():
    """Direct import of get_tld must succeed (fix for Bug #03)."""
    from tld import get_tld  # noqa: F401


def test_trafilatura_courlan_import_chain():
    """Ensure the trafilatura -> courlan -> tld import chain works."""
    import trafilatura

    # Using trafilatura should not raise import errors
    assert trafilatura is not None


def test_web_scraper_lazy_import_no_error():
    """Calling _get_trafilatura() should not raise import errors."""
    from teddy_executor.adapters.outbound.web_scraper_adapter import (
        WebScraperAdapter,
    )

    adapter = WebScraperAdapter(config_service=None)
    trafilatura = adapter._get_trafilatura()
    assert trafilatura is not None
    # Try actual extraction from minimal HTML
    html = "<html><body><p>Test content</p></body></html>"
    result = trafilatura.extract(html, output_format="markdown")
    assert result is not None
    assert "Test content" in result
