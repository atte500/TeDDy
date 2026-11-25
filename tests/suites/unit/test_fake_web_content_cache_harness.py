"""Harness tests for ``FakeWebContentCache``."""

import pytest

from teddy_executor.core.domain.models.exceptions import WebContentCacheError
from teddy_executor.core.ports.outbound import IWebContentCache
from tests.harness.setup.fake_web_content_cache import FakeWebContentCache

SESSION_ROOT = ".teddy/sessions/demo"
PDF_URL = "https://example.com/a.pdf"
OTHER_PDF_URL = "https://example.com/b.pdf"


def test_load_entries_returns_the_scripted_map():
    fake = FakeWebContentCache(entries={PDF_URL: "alpha"})

    assert fake.load_entries(SESSION_ROOT) == {PDF_URL: "alpha"}
    assert fake.load_calls == [SESSION_ROOT]


def test_merge_entries_makes_the_body_visible_to_a_later_load():
    fake = FakeWebContentCache()

    fake.merge_entries(SESSION_ROOT, {PDF_URL: "alpha"})

    assert fake.merge_calls == [(SESSION_ROOT, {PDF_URL: "alpha"})]
    assert fake.load_entries(SESSION_ROOT) == {PDF_URL: "alpha"}


def test_merge_entries_keeps_sibling_entries():
    fake = FakeWebContentCache(entries={PDF_URL: "alpha"})

    fake.merge_entries(SESSION_ROOT, {OTHER_PDF_URL: "beta"})

    assert fake.load_entries(SESSION_ROOT) == {PDF_URL: "alpha", OTHER_PDF_URL: "beta"}


def test_absent_session_reads_empty_and_accepts_no_merge():
    fake = FakeWebContentCache()

    assert fake.load_entries(None) == {}
    fake.merge_entries(None, {PDF_URL: "alpha"})

    assert fake.merge_calls == [(None, {PDF_URL: "alpha"})]
    assert fake.load_entries(SESSION_ROOT) == {}


def test_merge_entries_raises_the_scripted_error_and_keeps_the_map_intact():
    error = WebContentCacheError("cannot persist cache", session_root=SESSION_ROOT)
    fake = FakeWebContentCache(entries={PDF_URL: "alpha"}, merge_error=error)

    with pytest.raises(WebContentCacheError):
        fake.merge_entries(SESSION_ROOT, {OTHER_PDF_URL: "beta"})

    assert fake.load_entries(SESSION_ROOT) == {PDF_URL: "alpha"}


def test_fake_satisfies_the_cache_port():
    assert isinstance(FakeWebContentCache(), IWebContentCache)


def test_fake_web_content_cache_fixture_registers_in_container(
    container, fake_web_content_cache
):
    assert container.resolve(IWebContentCache) is fake_web_content_cache
