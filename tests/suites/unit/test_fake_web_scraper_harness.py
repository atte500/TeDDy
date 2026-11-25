"""Harness tests for ``FakeWebScraper``."""

import pytest

from teddy_executor.core.ports.outbound import IWebScraper
from tests.harness.setup.fake_web_scraper import FakeWebScraper

PDF_URL = "https://example.com/a.pdf"
OTHER_PDF_URL = "https://example.com/b.pdf"


def test_get_content_returns_the_scripted_body():
    fake = FakeWebScraper(contents={PDF_URL: "alpha"})

    assert fake.get_content(PDF_URL) == "alpha"
    assert fake.calls == [(PDF_URL, True, {})]


def test_get_content_records_the_truncate_flag():
    fake = FakeWebScraper(contents={PDF_URL: "alpha"})

    assert fake.get_content(PDF_URL, truncate=False) == "alpha"
    assert fake.calls == [(PDF_URL, False, {})]


def test_get_content_raises_the_scripted_failure():
    failure = TimeoutError("network unreachable")
    fake = FakeWebScraper(failures={PDF_URL: failure})

    with pytest.raises(TimeoutError):
        fake.get_content(PDF_URL)

    assert fake.calls == [(PDF_URL, True, {})]


def test_unscripted_url_is_rejected_loudly():
    fake = FakeWebScraper(contents={PDF_URL: "alpha"})

    with pytest.raises(AssertionError, match=OTHER_PDF_URL):
        fake.get_content(OTHER_PDF_URL)


def test_fake_satisfies_the_scraper_port():
    assert isinstance(FakeWebScraper(), IWebScraper)


def test_fake_web_scraper_fixture_registers_in_container(container, fake_web_scraper):
    assert container.resolve(IWebScraper) is fake_web_scraper
