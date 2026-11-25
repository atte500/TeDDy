"""Integration tests for the filesystem session content cache adapter.

The adapter alone knows how the cache is persisted, so these tests drive it
against a real temporary directory instead of the in-memory fake the
coordinator's suite uses.
"""

import json
import threading
from pathlib import Path

import pytest

from teddy_executor.adapters.outbound.web_content_cache_adapter import (
    WebContentCacheAdapter,
)
from teddy_executor.core.domain.models.exceptions import WebContentCacheError

PDF_URL = "https://example.com/report.pdf"
OTHER_URL = "https://example.com/other.pdf"
CONCURRENT_WRITERS = 8
BARRIER_TIMEOUT_SECONDS = 5


def _cache_path(session_root: Path) -> Path:
    return session_root / WebContentCacheAdapter.CACHE_FILENAME


def _directory_entries(session_root: Path) -> list[str]:
    return sorted(path.name for path in session_root.iterdir())


def test_missing_cache_reads_as_empty(tmp_path):
    assert WebContentCacheAdapter().load_entries(str(tmp_path)) == {}


@pytest.mark.parametrize(
    "payload",
    [
        "{not json at all",
        "[]",
        '"a bare string"',
        '{"https://example.com/report.pdf": 5}',
    ],
    ids=["unparseable", "list-root", "string-root", "non-string-value"],
)
def test_damaged_cache_reads_as_empty(tmp_path, payload):
    _cache_path(tmp_path).write_text(payload, encoding="utf-8")

    assert WebContentCacheAdapter().load_entries(str(tmp_path)) == {}


def test_absent_session_reads_empty_and_writes_nothing(tmp_path):
    session_root = tmp_path / "sessions" / "demo"
    adapter = WebContentCacheAdapter()

    assert adapter.load_entries(None) == {}
    adapter.merge_entries(None, {PDF_URL: "alpha"})

    assert not session_root.exists(), (
        "a session-agnostic export must create neither directory nor file"
    )


def test_merge_creates_the_session_directory_and_keeps_siblings(tmp_path):
    session_root = str(tmp_path / "sessions" / "demo")
    adapter = WebContentCacheAdapter()

    adapter.merge_entries(session_root, {PDF_URL: "alpha"})
    adapter.merge_entries(session_root, {OTHER_URL: "beta"})

    assert adapter.load_entries(session_root) == {
        PDF_URL: "alpha",
        OTHER_URL: "beta",
    }, "a later merge must layer over the stored map instead of replacing it"


def test_merge_persists_a_flat_utf8_json_map(tmp_path):
    session_root = tmp_path / "demo"
    body = "Grüße aus dem Bericht"

    WebContentCacheAdapter().merge_entries(str(session_root), {PDF_URL: body})

    on_disk = _cache_path(session_root).read_text(encoding="utf-8")
    assert json.loads(on_disk) == {PDF_URL: body}
    assert "\r" not in on_disk, "the cache must be written without newline translation"


def test_merge_leaves_no_temporary_sibling(tmp_path):
    session_root = tmp_path / "demo"

    WebContentCacheAdapter().merge_entries(str(session_root), {PDF_URL: "alpha"})

    assert _directory_entries(session_root) == [
        WebContentCacheAdapter.CACHE_FILENAME
    ], "a completed merge must leave only the cache file behind"


def test_unusable_session_root_raises_a_cache_error_naming_it(tmp_path):
    session_root = tmp_path / "not-a-directory"
    session_root.write_text("occupied", encoding="utf-8")

    with pytest.raises(WebContentCacheError) as exc_info:
        WebContentCacheAdapter().merge_entries(str(session_root), {PDF_URL: "alpha"})

    assert exc_info.value.session_root == str(session_root)


def test_failed_replace_raises_and_leaves_no_temporary_sibling(tmp_path):
    session_root = tmp_path / "demo"
    adapter = WebContentCacheAdapter()
    adapter.merge_entries(str(session_root), {PDF_URL: "alpha"})
    occupied = _cache_path(session_root)
    occupied.unlink()
    occupied.mkdir()
    (occupied / "holder").write_text("x", encoding="utf-8")

    with pytest.raises(WebContentCacheError):
        adapter.merge_entries(str(session_root), {OTHER_URL: "beta"})

    assert _directory_entries(session_root) == [
        WebContentCacheAdapter.CACHE_FILENAME
    ], "a failed replace must not strand the temporary sibling"


def test_concurrent_merges_from_separate_instances_keep_every_entry(tmp_path):
    session_root = str(tmp_path / "demo")
    urls = [f"https://example.com/{index}.pdf" for index in range(CONCURRENT_WRITERS)]
    barrier = threading.Barrier(CONCURRENT_WRITERS, timeout=BARRIER_TIMEOUT_SECONDS)
    failures: list[Exception] = []

    def merge(url: str) -> None:
        adapter = WebContentCacheAdapter()
        try:
            barrier.wait()
            adapter.merge_entries(session_root, {url: f"body of {url}"})
        except Exception as exc:  # recorded so a thread failure fails the test
            failures.append(exc)

    threads = [threading.Thread(target=merge, args=(url,)) for url in urls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=BARRIER_TIMEOUT_SECONDS)

    assert failures == [], "every concurrent merge must succeed"
    assert WebContentCacheAdapter().load_entries(session_root) == {
        url: f"body of {url}" for url in urls
    }, "a merge must not drop an entry a sibling instance wrote concurrently"
