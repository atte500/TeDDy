"""Regression tests: thread-safe logging suppression in WebScraperAdapter.

`WebScraperAdapter.get_content()` suppresses trafilatura's WARNING-level
"discarding data" logs by toggling the process-global logging threshold
(`logging.disable`). Under concurrent callers — ContextService fetches
context URLs via a ThreadPoolExecutor — a bare enter/restore toggle is
racy: the first caller to exit restores the threshold while siblings are
still inside trafilatura.extract(), letting their warnings escape to the
terminal via the root logger.

These tests reproduce the deterministic interleaving against a local HTTP
server serving a non-extractable page, and assert that no trafilatura
records escape the suppression wrapper.
"""

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter


FAST_DELAY = "0.15"  # worker 0 finishes early -> restores the threshold first
SLOW_DELAY = "0.7"  # workers 1-5 are still extracting after the restore
WORKERS = 6

# HTML that trafilatura cannot extract -> triggers its "discarding data" warning.
NON_EXTRACTABLE_PAGE = (
    b"<html><head></head><body><script>var a=1;</script></body></html>"
)


class _CaptureHandler(logging.Handler):
    """Collects messages of records emitted through the 'trafilatura' logger.

    trafilatura attaches a NullHandler to its own logger, so stderr/lastResort
    capture is blind in bare processes. Attaching here captures records at the
    emitting logger; the logging.disable() threshold gates records BEFORE
    handlers are consulted, so a captured record proves the global threshold
    was open at emission time.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture()
def scraper_server():
    """Local ThreadingHTTPServer serving a non-extractable page.

    Optional ?d=<seconds> query parameter delays the response to force the
    deterministic worker interleaving.
    """

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            delay = float(parse_qs(parsed.query).get("d", ["0.05"])[0])
            time.sleep(delay)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(NON_EXTRACTABLE_PAGE)))
            self.end_headers()
            self.wfile.write(NON_EXTRACTABLE_PAGE)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture()
def trafilatura_capture():
    handler = _CaptureHandler()
    logger = logging.getLogger("trafilatura")
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


def test_single_threaded_call_does_not_leak_trafilatura_warnings(
    scraper_server, trafilatura_capture
):
    """Control: the suppression wrapper holds for a single sequential call."""
    adapter = WebScraperAdapter(config_service=None)
    adapter.get_content(f"{scraper_server}/page")
    assert trafilatura_capture.messages == []


def test_concurrent_calls_keep_threshold_closed_until_all_callers_exit(
    scraper_server, trafilatura_capture
):
    """Concurrent get_content() calls must not leak trafilatura warnings.

    Six barrier-synchronized workers call get_content(); worker 0 gets a fast
    response so its suppression-scope exit fires while workers 1-5 are still
    inside trafilatura.extract(). With the racy enter/restore toggle, the
    fast worker's restore re-opens the process-global threshold and the slow
    workers' warnings escape; every escaped record is captured here.
    """
    adapter = WebScraperAdapter(config_service=None)
    barrier = threading.Barrier(WORKERS)

    def worker(i: int) -> None:
        delay = FAST_DELAY if i == 0 else SLOW_DELAY
        barrier.wait(timeout=10)
        adapter.get_content(f"{scraper_server}/page?d={delay}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "worker did not finish within timeout"

    assert trafilatura_capture.messages == [], (
        "trafilatura warnings escaped the suppression wrapper under concurrent "
        f"calls: {trafilatura_capture.messages}"
    )
