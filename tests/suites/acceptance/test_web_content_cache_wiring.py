"""Tracer-bullet acceptance tests for the session content cache wiring.

Context assembly is driven through ``IGetContextUseCase`` as resolved from the
real composition root, so the adapter, the coordinator, and the service graph
they join are exercised end to end instead of hand-constructed. The scraper and
cache fakes are registered as instances on that container because a fixture
hands back an unscripted double and neither fake exposes a scripting method.
"""

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import IWebContentCache, IWebScraper
from tests.harness.setup.fake_web_content_cache import FakeWebContentCache
from tests.harness.setup.fake_web_scraper import FakeWebScraper

PDF_URL = "https://example.com/report.pdf"
SESSION_ROOT = ".teddy/sessions/demo/first"
FETCHED_BODY = "alpha body"
CACHED_BODY = "beta body"


def _assemble(container, url: str, session_root: str):
    return container.resolve(IGetContextUseCase).get_context(
        context_files={"Turn": [url]},
        include_tokens=False,
        session_root=session_root,
    )


def test_assembly_fetches_verbatim_and_merges_the_body(
    container,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
    mock_config,
):
    scraper = FakeWebScraper(contents={PDF_URL: FETCHED_BODY})
    cache = FakeWebContentCache()
    container.register(IWebScraper, instance=scraper)
    container.register(IWebContentCache, instance=cache)

    context = _assemble(container, PDF_URL, SESSION_ROOT)

    assert FETCHED_BODY in context.content, (
        "the fetched body must render in the assembled payload"
    )
    assert scraper.calls == [(PDF_URL, False, {})], (
        "assembly must fetch the body verbatim, never ask the scraper to truncate"
    )
    assert cache.load_calls == [SESSION_ROOT], (
        "assembly must load the session map once, keyed by the session root"
    )
    assert cache.merge_calls == [(SESSION_ROOT, {PDF_URL: FETCHED_BODY})], (
        "the successful body must be merged back in one batch"
    )


def test_assembly_serves_a_cached_body_without_a_fetch(
    container,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
    mock_config,
):
    scraper = FakeWebScraper(contents={PDF_URL: FETCHED_BODY})
    cache = FakeWebContentCache(entries={PDF_URL: CACHED_BODY})
    container.register(IWebScraper, instance=scraper)
    container.register(IWebContentCache, instance=cache)

    context = _assemble(container, PDF_URL, SESSION_ROOT)

    assert CACHED_BODY in context.content, (
        "a cached URL must render from the session map"
    )
    assert FETCHED_BODY not in context.content, "a cached URL must not be refetched"
    assert scraper.calls == [], "a cached URL must cost no network round trip"
    assert cache.merge_calls == [], "a cache hit must write nothing back"


def test_failed_fetch_renders_the_missing_marker_and_merges_nothing(
    container,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
    mock_config,
):
    scraper = FakeWebScraper(failures={PDF_URL: TimeoutError("unreachable")})
    cache = FakeWebContentCache()
    container.register(IWebScraper, instance=scraper)
    container.register(IWebContentCache, instance=cache)

    context = _assemble(container, PDF_URL, SESSION_ROOT)

    assert "--- FILE NOT FOUND ---" in context.content, (
        "a failed fetch must render the existing missing marker"
    )
    assert cache.load_calls == [SESSION_ROOT], (
        "assembly must consult the session map even when the fetch fails"
    )
    assert cache.merge_calls == [], (
        "a failed fetch must leave no cache entry, so a later turn retries"
    )
