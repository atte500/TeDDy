"""Unit tests for the coordinator owning the cached remote-fetch workflow."""

import threading
from typing import Any, Mapping

import pytest

from teddy_executor.core.domain.models.config_schema import ReadConfig
from teddy_executor.core.domain.models.exceptions import (
    PdfExtractionError,
    WebContentCacheError,
)
from teddy_executor.core.services.web_content_service import WebContentService
from teddy_executor.core.utils.pdf import cap_extracted_text
from tests.harness.setup.fake_web_content_cache import FakeWebContentCache
from tests.harness.setup.fake_web_scraper import FakeWebScraper

PDF_URL = "https://example.com/report.pdf"
OTHER_URL = "https://example.com/other.pdf"
SESSION_ROOT = ".teddy/sessions/demo/first"
TEN_LINE_BODY = "\n".join(f"line {index}" for index in range(1, 11))
BARRIER_TIMEOUT_SECONDS = 5


class _BudgetConfig:
    """Serves one read budget through the config service setting shape."""

    def __init__(self, max_lines: int) -> None:
        self._max_lines = max_lines

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._max_lines if key == "read.max_lines" else default


class _ConcurrencyProbeScraper:
    """Fails unless every URL's fetch is in flight at the same moment.

    Each call parks on a shared barrier, so a sequential coordinator blocks
    until the barrier breaks while a concurrent one releases it immediately.
    The peak in-flight count is the assertion's subject; the timeout only
    bounds a failing run.
    """

    def __init__(self, contents: Mapping[str, str]) -> None:
        self._contents = dict(contents)
        self._lock = threading.Lock()
        parties = len(self._contents)
        self._barrier = threading.Barrier(parties, timeout=BARRIER_TIMEOUT_SECONDS)
        self._in_flight = 0
        self.max_in_flight = 0

    def get_content(self, url: str, **_kwargs: Any) -> str:
        with self._lock:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        self._barrier.wait()
        with self._lock:
            self._in_flight -= 1
        return self._contents[url]


def _service(scraper, cache, config=None) -> WebContentService:
    return WebContentService(web_scraper=scraper, cache=cache, config_service=config)


def test_cached_body_is_served_without_a_fetch():
    scraper = FakeWebScraper(contents={PDF_URL: "fresh body"})
    cache = FakeWebContentCache(entries={PDF_URL: "cached body"})

    result = _service(scraper, cache).fetch_one(PDF_URL, session_root=SESSION_ROOT)

    assert result == "cached body"
    assert scraper.calls == []
    assert cache.merge_calls == []


def test_capped_read_returns_the_announced_cap_and_stores_the_full_body():
    scraper = FakeWebScraper(contents={PDF_URL: TEN_LINE_BODY})
    cache = FakeWebContentCache()

    result = _service(scraper, cache, _BudgetConfig(3)).fetch_one(
        PDF_URL, session_root=SESSION_ROOT
    )

    # The expectation comes from the shared announced-cap helper, so the
    # notice text keeps a single owner.
    assert result == cap_extracted_text(TEN_LINE_BODY, 3)
    assert scraper.calls == [(PDF_URL, {})]
    assert cache.merge_calls == [(SESSION_ROOT, {PDF_URL: TEN_LINE_BODY})]


def test_capped_read_caps_a_cached_body_too():
    scraper = FakeWebScraper(contents={PDF_URL: "fresh body"})
    cache = FakeWebContentCache(entries={PDF_URL: TEN_LINE_BODY})

    result = _service(scraper, cache, _BudgetConfig(3)).fetch_one(
        PDF_URL, session_root=SESSION_ROOT
    )

    assert result == cap_extracted_text(TEN_LINE_BODY, 3)
    assert scraper.calls == []


def test_uncapped_read_returns_the_full_body():
    scraper = FakeWebScraper(contents={PDF_URL: TEN_LINE_BODY})
    cache = FakeWebContentCache()

    result = _service(scraper, cache, _BudgetConfig(3)).fetch_one(
        PDF_URL, session_root=SESSION_ROOT, truncate=False
    )

    assert result == TEN_LINE_BODY


def test_default_budget_comes_from_the_schema_when_no_config_is_injected():
    body = "\n".join(f"line {index}" for index in range(1, ReadConfig.max_lines + 2))
    scraper = FakeWebScraper(contents={PDF_URL: body})
    cache = FakeWebContentCache()

    result = _service(scraper, cache).fetch_one(PDF_URL, session_root=SESSION_ROOT)

    assert result == cap_extracted_text(body, ReadConfig.max_lines)


def test_failed_fetch_propagates_and_merges_nothing():
    failure = PdfExtractionError("not a pdf", source=PDF_URL)
    scraper = FakeWebScraper(failures={PDF_URL: failure})
    cache = FakeWebContentCache()

    with pytest.raises(PdfExtractionError):
        _service(scraper, cache).fetch_one(PDF_URL, session_root=SESSION_ROOT)

    assert cache.merge_calls == []


def test_cache_write_failure_still_returns_the_fetched_body():
    error = WebContentCacheError("cannot persist", session_root=SESSION_ROOT)
    scraper = FakeWebScraper(contents={PDF_URL: "fresh body"})
    cache = FakeWebContentCache(merge_error=error)

    result = _service(scraper, cache).fetch_one(PDF_URL, session_root=SESSION_ROOT)

    assert result == "fresh body"


def test_absent_session_fetches_without_touching_the_session_map():
    scraper = FakeWebScraper(contents={PDF_URL: "fresh body"})
    cache = FakeWebContentCache()

    result = _service(scraper, cache).fetch_one(PDF_URL)

    assert result == "fresh body"
    assert scraper.calls == [(PDF_URL, {})]
    assert cache.load_calls == [None]
    assert cache.load_entries(SESSION_ROOT) == {}


def test_batch_loads_the_session_map_once():
    scraper = FakeWebScraper(contents={PDF_URL: "alpha", OTHER_URL: "beta"})
    cache = FakeWebContentCache()

    bodies = _service(scraper, cache).fetch_many(
        [PDF_URL, OTHER_URL], session_root=SESSION_ROOT
    )

    assert cache.load_calls == [SESSION_ROOT]
    assert bodies == {PDF_URL: "alpha", OTHER_URL: "beta"}
    assert cache.merge_calls == [(SESSION_ROOT, {PDF_URL: "alpha", OTHER_URL: "beta"})]


def test_batch_fetches_a_duplicate_url_once():
    scraper = FakeWebScraper(contents={PDF_URL: "alpha"})
    cache = FakeWebContentCache()

    bodies = _service(scraper, cache).fetch_many(
        [PDF_URL, PDF_URL], session_root=SESSION_ROOT
    )

    assert scraper.calls == [(PDF_URL, {})]
    assert bodies == {PDF_URL: "alpha"}


def test_batch_maps_a_failed_url_to_none_and_merges_only_successes():
    failure = TimeoutError("unreachable")
    scraper = FakeWebScraper(contents={OTHER_URL: "beta"}, failures={PDF_URL: failure})
    cache = FakeWebContentCache()

    bodies = _service(scraper, cache).fetch_many(
        [PDF_URL, OTHER_URL], session_root=SESSION_ROOT
    )

    assert bodies == {PDF_URL: None, OTHER_URL: "beta"}
    assert cache.merge_calls == [(SESSION_ROOT, {OTHER_URL: "beta"})]


def test_batch_never_caps_a_body():
    scraper = FakeWebScraper(contents={PDF_URL: TEN_LINE_BODY})
    cache = FakeWebContentCache()

    bodies = _service(scraper, cache, _BudgetConfig(3)).fetch_many(
        [PDF_URL], session_root=SESSION_ROOT
    )

    assert bodies == {PDF_URL: TEN_LINE_BODY}


def test_batch_fetches_misses_concurrently():
    probe = _ConcurrencyProbeScraper({PDF_URL: "alpha", OTHER_URL: "beta"})
    cache = FakeWebContentCache()

    bodies = _service(probe, cache).fetch_many(
        [PDF_URL, OTHER_URL], session_root=SESSION_ROOT
    )

    assert bodies == {PDF_URL: "alpha", OTHER_URL: "beta"}, (
        "every uncached URL must resolve; a broken barrier means the fetches "
        "never overlapped"
    )
    assert probe.max_in_flight == 2, (
        "uncached URLs must be fetched concurrently, not one after another"
    )
