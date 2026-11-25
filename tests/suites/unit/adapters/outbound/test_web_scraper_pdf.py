"""The scraper routes a PDF URL through the injected IPdfExtractor."""

import pytest

from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.core.ports.outbound import IConfigService
from tests.harness.setup.fake_pdf_extractor import FakePdfExtractor
from tests.harness.setup.mocking import POSIXPathMock


def _build_adapter(extractor, config=None):
    adapter = WebScraperAdapter(config_service=config, pdf_extractor=extractor)
    # Keep the Red run hermetic: the un-routed branch must never hit the network.
    adapter._fetch_with_rotation = POSIXPathMock(return_value=None)
    return adapter


def test_pdf_url_is_fetched_as_bytes_and_extracted():
    extractor = FakePdfExtractor("Extracted PDF body")
    payload = b"%PDF-1.4\nbody"
    adapter = _build_adapter(extractor)
    adapter._fetch_pdf_bytes = POSIXPathMock(return_value=payload)

    result = adapter.get_content("https://example.com/report.pdf")

    assert result == "Extracted PDF body"
    assert extractor.calls == [(payload, "https://example.com/report.pdf")]


def test_signed_pdf_url_keeps_the_full_source():
    extractor = FakePdfExtractor("Signed body")
    adapter = _build_adapter(extractor)
    adapter._fetch_pdf_bytes = POSIXPathMock(return_value=b"%PDF-1.4\n")

    url = "https://example.com/report.pdf?token=abc"
    result = adapter.get_content(url)

    assert result == "Signed body"
    assert extractor.calls == [(b"%PDF-1.4\n", url)]


def test_pdf_text_layer_ignores_the_configured_read_cap():
    text = "\n".join(f"line{i}" for i in range(1, 6))
    config = POSIXPathMock(spec=IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        3 if key == "read.max_lines" else default
    )
    adapter = _build_adapter(FakePdfExtractor(text), config)
    adapter._fetch_pdf_bytes = POSIXPathMock(return_value=b"%PDF-1.4\n")

    result = adapter.get_content("https://example.com/report.pdf")

    assert result == text


def test_non_pdf_url_is_not_routed_through_the_extractor():
    extractor = FakePdfExtractor()
    adapter = _build_adapter(extractor)
    adapter._fetch_with_rotation = POSIXPathMock(return_value="<html>page</html>")
    trafilatura = POSIXPathMock()
    trafilatura.extract.return_value = "markdown body"
    adapter._get_trafilatura = POSIXPathMock(return_value=trafilatura)

    result = adapter.get_content("https://example.com/page")

    assert result == "markdown body"
    assert extractor.calls == []


def test_pdf_url_requires_the_extractor_port():
    adapter = _build_adapter(None)

    with pytest.raises(AssertionError, match="pdf_extractor"):
        adapter.get_content("https://example.com/report.pdf")
