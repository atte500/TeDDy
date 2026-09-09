#!/usr/bin/env python3
"""
Probe to measure per-URL fetch times using the project's WebScraperAdapter.
This simulates the per-turn blocking behavior in context_service.py.
Run from project root: uv run python spikes/debug/probe_url_fetch.py
"""
import time
import sys
import os
import platform

# Ensure we can import the adapter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def main():
    from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter

    print("=== URL Fetch Timing Probe ===")
    print(f"Host OS: {platform.platform()}")
    print(f"Python: {sys.version}")
    print()

    adapter = WebScraperAdapter()

    # Test URLs: mix of fast fail, slow success, timeout scenarios
    urls = [
        ("Fast HTTP 404", "https://httpstat.us/404"),
        ("Fast HTTP 500", "https://httpstat.us/500"),
        ("Slow success (2s)", "https://httpstat.us/200?sleep=2000"),
        ("Timeout (nonexistent domain)", "https://nonexistent-domain-for-probe-xyz123.com/"),
        ("Real page (wikipedia)", "https://de.wikipedia.org/wiki/Bergfreunde"),
    ]

    for label, url in urls:
        print(f"--- {label} ---")
        print(f"URL: {url}")
        start = time.perf_counter()
        try:
            content = adapter.get_content(url)
            elapsed = time.perf_counter() - start
            content_len = len(content) if content else 0
            print(f"  RESULT: SUCCESS, {elapsed*1000:.0f}ms, content_len={content_len}")
        except Exception as e:
            elapsed = time.perf_counter() - start
            etype = type(e).__name__
            emsg = str(e)[:100]
            print(f"  RESULT: ERROR {etype}, {elapsed*1000:.0f}ms, {emsg}")
        print()

    print("=== End Probe ===")

if __name__ == "__main__":
    main()