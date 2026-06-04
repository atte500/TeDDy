#!/usr/bin/env python3
"""
Standalone Feature Prototype: 02-09 Session Web Content Caching
===============================================================
De-risks the web content caching design for Slice 02-09.

Validates:
1. cache_dir parameter flow → ContextService.get_context()
2. Atomic JSON cache file read/write (.web_cache.json)
3. Cache hit/miss lifecycle (fetch once, serve from cache)
4. Cache corruption handling (malformed JSON → graceful fallback)
5. Backward compatibility (no cache_dir → no caching)
6. Network failure handling (errors are NOT cached)
7. SessionOrchestrator path derivation (plan_path → session_root)

Usage:
    # Interactive showcase (default)
    poetry run python spikes/prototypes/02-09-web-content-caching.py

    # Non-interactive verification (all assertions)
    poetry run python spikes/prototypes/02-09-web-content-caching.py --verify

    # Interactive boot check (5-second smoke test)
    timeout 5 poetry run python spikes/prototypes/02-09-web-content-caching.py <<< "q" || echo "Clean exit"
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# CONSTANTS
# ============================================================

CACHE_FILENAME = ".web_cache.json"
CACHE_TEMP_SUFFIX = ".tmp"
SCENARIO_SEPARATOR = "─" * 60


# ============================================================
# CACHE IMPLEMENTATION
# ============================================================
# Mirrors the exact logic that would be added to ContextService.
# Uses real pathlib + json for file operations; Path.replace() for atomic writes.

class WebContentCache:
    """
    Session-level web content cache.

    Lifecycle:
        - Load cache from disk on first access (lazy)
        - Check cache before calling IWebScraper
        - Store in cache after successful fetch
        - Write atomically to prevent corruption on crash
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self._cache_dir: Optional[str] = cache_dir
        self._cache: Dict[str, str] = {}
        self._loaded: bool = False
        self._fetch_count: int = 0
        self._corruption_warning: bool = False

    # ── Public API ──────────────────────────────────────────

    def get_cached_content(self, url: str) -> Optional[str]:
        """Return cached content for url, or None if missing/cache disabled."""
        if not self._cache_dir:
            return None
        self._ensure_loaded()
        return self._cache.get(url)

    def store_cached_content(self, url: str, content: str) -> None:
        """Cache content and persist atomically to disk."""
        if not self._cache_dir:
            return
        self._ensure_loaded()
        self._cache[url] = content
        self._save_atomically()

    def fetch_and_cache(self, url: str, fetch_fn: Callable[[str], str]) -> str:
        """Fetch content from web, cache it atomically, return content."""
        content = fetch_fn(url)
        self._fetch_count += 1
        self.store_cached_content(url, content)
        return content

    # ── Properties ──────────────────────────────────────────

    @property
    def fetch_count(self) -> int:
        return self._fetch_count

    @property
    def corruption_warning_issued(self) -> bool:
        return self._corruption_warning

    @property
    def is_enabled(self) -> bool:
        return self._cache_dir is not None

    @property
    def cache_path(self) -> Optional[Path]:
        """Full path to the cache file, or None if caching disabled."""
        if not self._cache_dir:
            return None
        return Path(self._cache_dir) / CACHE_FILENAME

    # ── Internal ────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Lazy-load cache from disk. On corruption, treat as empty."""
        if self._loaded or not self._cache_dir:
            return
        self._loaded = True
        cache_path = self.cache_path
        if not cache_path or not cache_path.exists():
            self._cache = {}
            return
        try:
            raw = cache_path.read_text(encoding="utf-8")
            parsed: object = json.loads(raw)
            if not isinstance(parsed, dict):
                self._corruption_warning = True
                self._cache = {}
                return
            # Validate all values are strings
            for k, v in parsed.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    self._corruption_warning = True
                    self._cache = {}
                    return
            self._cache = parsed
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            self._corruption_warning = True
            self._cache = {}

    def _save_atomically(self) -> None:
        """
        Atomic write: write to temp file, then rename to target.

        This prevents partial writes from corrupting the cache
        if the process crashes mid-write.
        """
        if not self._cache_dir:
            return
        cache_dir_path = Path(self._cache_dir)
        cache_dir_path.mkdir(parents=True, exist_ok=True)
        target = cache_dir_path / CACHE_FILENAME
        tmp = cache_dir_path / f"{CACHE_FILENAME}{CACHE_TEMP_SUFFIX}"

        # Write to temp file
        tmp.write_text(
            json.dumps(self._cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Atomic rename (atomically replaces target on all platforms)
        tmp.replace(target)

    def __repr__(self) -> str:
        if not self._cache_dir:
            return "WebContentCache(disabled)"
        return (
            f"WebContentCache(dir={self._cache_dir!r}, "
            f"entries={len(self._cache)}, "
            f"fetches={self._fetch_count})"
        )


# ============================================================
# SESSION ORCHESTRATOR PATH DERIVATION
# ============================================================
# Mirrors the logic in SessionOrchestrator._is_session_mode / execute:
#   1. plan_path = str(turn_dir / "plan.md")        # e.g. .../mysession/01/plan.md
#   2. turn_root = Path(plan_path).parent            # .../mysession/01
#   3. session_root = turn_root.parent                # .../mysession
#   4. cache_dir = str(session_root)                  # .../mysession (where .web_cache.json lives)

def derive_cache_dir(plan_path: str) -> str:
    """Derive cache directory from plan_path, matching SessionOrchestrator logic."""
    return str(Path(plan_path).parent.parent)


# ============================================================
# SCENARIO RUNNER
# ============================================================

class ScenarioRunner:
    """Manages a temporary workspace and runs all scenarios."""

    def __init__(self) -> None:
        self._temp_dir: Optional[str] = None

    def __enter__(self) -> "ScenarioRunner":
        self._temp_dir = tempfile.mkdtemp(prefix="web_cache_proto_")
        return self

    def __exit__(self, *args: object) -> None:
        if self._temp_dir:
            shutil.rmtree(self._temp_dir)

    @property
    def workspace(self) -> str:
        assert self._temp_dir is not None
        return self._temp_dir

    def create_session(self, name: str = "test-session") -> str:
        """Create a session directory structure and return the session root path."""
        session_root = Path(self.workspace) / "sessions" / name
        turn_dir = session_root / "01"
        turn_dir.mkdir(parents=True, exist_ok=True)
        plan_path = turn_dir / "plan.md"
        plan_path.write_text("# Test Plan\n", encoding="utf-8")
        return str(session_root)

    # ── Scenario 1: Cache Hit ──────────────────────────────

    def scenario_cache_hit(self) -> Dict[str, Any]:
        """
        Pre-populate cache → get_cached_content returns cached content
        without calling the web scraper.
        """
        session_root = self.create_session("cache-hit")
        cache = WebContentCache(cache_dir=session_root)
        url = "https://example.com/page"

        # Pre-seed cache
        cache.store_cached_content(url, "cached response")
        pre_fetch_count = cache.fetch_count

        # This should NEVER be called if cache works
        def failing_fetch(_url: str) -> str:
            msg = "Web fetch was triggered despite cache hit!"
            raise RuntimeError(msg)

        cached = cache.get_cached_content(url)
        assert cached == "cached response", f"Expected 'cached response', got {cached!r}"
        assert cache.fetch_count == pre_fetch_count, (
            f"Fetch count increased despite cache hit: "
            f"{cache.fetch_count} != {pre_fetch_count}"
        )

        # Verify cache file exists on disk with correct content
        cache_file = Path(session_root) / CACHE_FILENAME
        assert cache_file.exists(), "Cache file should exist after store"
        disk_content = json.loads(cache_file.read_text(encoding="utf-8"))
        assert disk_content.get(url) == "cached response", (
            f"Disk cache mismatch: {disk_content}"
        )

        print(f"    Cache file on disk: ✓ ({cache_file})")
        print(f"    Disk entries: {list(disk_content.keys())}")
        print(f"    Fetch count: {cache.fetch_count}")

        return {
            "scenario": "1. Cache Hit",
            "passed": True,
            "details": {
                "returned": cached,
                "fetch_count": cache.fetch_count,
                "disk_entry": disk_content.get(url),
            },
        }

    # ── Scenario 2: Cache Miss → Hit ───────────────────────

    def scenario_cache_miss_to_hit(self) -> Dict[str, Any]:
        """
        Empty cache → fetch from web → cache populated.
        Subsequent lookup is a cache hit (no fetch).
        """
        session_root = self.create_session("cache-miss-hit")
        cache = WebContentCache(cache_dir=session_root)
        url = "https://example.com/page"

        fetch_log: List[str] = []

        def mock_fetch(url: str) -> str:
            fetch_log.append(url)
            return "fresh content"

        # First access: cache miss → fetch
        content1 = cache.fetch_and_cache(url, mock_fetch)

        assert content1 == "fresh content", f"Expected 'fresh content', got {content1!r}"
        assert cache.fetch_count == 1, f"Should have fetched once, got {cache.fetch_count}"
        assert len(fetch_log) == 1

        # Second access: cache hit → no fetch
        content2 = cache.get_cached_content(url)
        assert content2 == "fresh content", f"Cache hit mismatch: {content2!r}"
        assert cache.fetch_count == 1, f"Fetch count should not increase: {cache.fetch_count}"
        assert len(fetch_log) == 1, f"Fetch log should still have 1 entry: {fetch_log}"

        # Third access: another cache hit
        content3 = cache.get_cached_content(url)
        assert content3 == "fresh content"
        assert cache.fetch_count == 1

        print(f"    First call: '{content1}' (fetch)")
        print(f"    Second call: '{content2}' (cache hit)")
        print(f"    Third call: '{content3}' (cache hit)")
        print(f"    Total fetch count: {cache.fetch_count}")

        return {
            "scenario": "2. Cache Miss → Hit",
            "passed": True,
            "details": {
                "first_content": content1,
                "second_content": content2,
                "third_content": content3,
                "fetch_count": cache.fetch_count,
                "total_web_calls": len(fetch_log),
            },
        }

    # ── Scenario 3: Cache Corruption ───────────────────────

    def scenario_cache_corruption(self) -> Dict[str, Any]:
        """
        Malformed cache file on disk → treated as empty cache.
        New content is fetched from web and stored fresh.
        """
        session_root = self.create_session("cache-corrupt")
        cache_file = Path(session_root) / CACHE_FILENAME

        # Write invalid JSON to simulate corruption
        cache_file.write_text('this is not valid json {{{', encoding="utf-8")
        print(f"    Corrupted cache file written ({len('this is not valid json {{{')} bytes)")

        cache = WebContentCache(cache_dir=session_root)

        # Should gracefully fall back to web fetch
        url = "https://example.com/page"
        fetch_log: List[str] = []

        def mock_fetch(url: str) -> str:
            fetch_log.append(url)
            return "recovered content"

        content = cache.fetch_and_cache(url, mock_fetch)
        assert content == "recovered content", f"Expected fresh fetch, got {content!r}"
        assert cache.corruption_warning_issued, "Should have logged corruption warning"
        assert cache.fetch_count == 1

        # After successful fetch, cache should be repaired and subsequent call is hit
        cached = cache.get_cached_content(url)
        assert cached == "recovered content", f"Cache hit after recovery failed: {cached!r}"

        # Verify disk is now valid JSON
        disk_raw = cache_file.read_text(encoding="utf-8")
        disk_parsed = json.loads(disk_raw)
        assert disk_parsed.get(url) == "recovered content"

        print(f"    First call: '{content}' (fetched after corruption)")
        print(f"    Second call: '{cached}' (cache hit after recovery)")
        print(f"    Disk now valid JSON: ✓")
        print(f"    Corruption warning logged: ✓")

        return {
            "scenario": "3. Cache Corruption Recovery",
            "passed": True,
            "details": {
                "content_after_corruption": content,
                "subsequent_hit": cached,
                "corruption_warning": cache.corruption_warning_issued,
                "fetch_count": cache.fetch_count,
                "disk_repaired": disk_parsed.get(url) == "recovered content",
            },
        }

    # ── Scenario 4: Backward Compatibility ─────────────────

    def scenario_backward_compatibility(self) -> Dict[str, Any]:
        """
        No cache_dir provided → every call fetches from web.
        No cache file is created on disk.
        This validates that existing callers (PlanningService, session_cli_handlers)
        are unaffected by the new feature.
        """
        cache = WebContentCache(cache_dir=None)
        url_a = "https://example.com/a"
        url_b = "https://example.com/b"

        fetch_log: List[str] = []

        def mock_fetch(url: str) -> str:
            fetch_log.append(url)
            return f"content from {url}"

        # Multiple calls to same URL should each fetch
        result1 = cache.fetch_and_cache(url_a, mock_fetch)
        result2 = cache.fetch_and_cache(url_a, mock_fetch)
        result3 = cache.fetch_and_cache(url_b, mock_fetch)

        assert cache.fetch_count == 3, (
            f"No cache means every call fetches: {cache.fetch_count}"
        )
        assert len(fetch_log) == 3
        assert result1 == "content from https://example.com/a"
        assert result2 == "content from https://example.com/a"
        assert result3 == "content from https://example.com/b"

        # No cache file should exist
        assert cache.cache_path is None, "cache_path should be None when disabled"
        assert not cache.is_enabled, "is_enabled should be False"

        print(f"    Call 1: '{result1}' (fetch)")
        print(f"    Call 2: '{result2}' (fetch again, no cache)")
        print(f"    Call 3: '{result3}' (fetch different URL)")
        print(f"    Total fetch count: {cache.fetch_count} (every call = fetch)")
        print(f"    Cache disabled: ✓")

        return {
            "scenario": "4. Backward Compatibility (no cache_dir)",
            "passed": True,
            "details": {
                "result_a_first": result1,
                "result_a_second": result2,
                "result_b": result3,
                "fetch_count": cache.fetch_count,
                "is_enabled": cache.is_enabled,
            },
        }

    # ── Scenario 5: Network Failure ────────────────────────

    def scenario_network_failure(self) -> Dict[str, Any]:
        """
        Network error during fetch → exception propagates to caller.
        Cache does NOT store an entry for the failed URL.
        Subsequent call retries the fetch.
        """
        session_root = self.create_session("network-fail")
        cache = WebContentCache(cache_dir=session_root)
        url = "https://example.com/page"

        # First attempt: network fails
        def failing_fetch(_url: str) -> str:
            msg = "ConnectionError: Network timeout"
            raise ConnectionError(msg)

        try:
            cache.fetch_and_cache(url, failing_fetch)
            assert False, "fetch_and_cache should have raised"
        except ConnectionError:
            pass

        # After failure, cache should NOT have the URL
        cached_after_failure = cache.get_cached_content(url)
        assert cached_after_failure is None, (
            f"Failed fetch should NOT be cached: {cached_after_failure!r}"
        )

        # Second attempt: should retry fetch (not served from cache)
        fetch_log: List[str] = []

        def succeeding_fetch(url: str) -> str:
            fetch_log.append(url)
            return "content after retry"

        # Reset fetch count for clarity (it was 0 since error was before increment)
        content = cache.fetch_and_cache(url, succeeding_fetch)
        assert content == "content after retry", f"Retry failed: {content!r}"
        assert len(fetch_log) == 1, "Should have re-fetched after failure"

        # Now it should be cached
        cached_after_success = cache.get_cached_content(url)
        assert cached_after_success == "content after retry"

        print(f"    After network error, cached: {cached_after_failure} (None = correct)")
        print(f"    Retry fetch succeeded: '{content}'")
        print(f"    After retry, cached: '{cached_after_success}'")

        return {
            "scenario": "5. Network Failure (error NOT cached)",
            "passed": True,
            "details": {
                "cached_after_failure": cached_after_failure,
                "retry_content": content,
                "cached_after_retry": cached_after_success,
                "fetch_count": cache.fetch_count,
            },
        }

    # ── Scenario 6: SessionOrchestrator Integration ────────

    def scenario_path_derivation(self) -> Dict[str, Any]:
        """
        Validate the plan_path → session_root → cache_dir derivation
        that SessionOrchestrator would use.
        """
        session_root = self.create_session("path-integration")
        turn_dir = Path(session_root) / "01"
        plan_path = turn_dir / "plan.md"

        # This is exactly how SessionOrchestrator derives cache_dir:
        #   turn_root = Path(plan_path).parent
        #   session_root = turn_root.parent
        #   cache_dir = str(session_root)
        cache_dir = derive_cache_dir(str(plan_path))

        assert cache_dir == str(Path(session_root)), (
            f"Path derivation mismatch:\n"
            f"  plan_path:  {plan_path}\n"
            f"  expected:   {session_root}\n"
            f"  derived:    {cache_dir}"
        )

        # Verify cache file ends up in the correct location
        cache = WebContentCache(cache_dir=cache_dir)
        cache.store_cached_content("https://example.com/page", "test content")

        expected_cache_path = Path(cache_dir) / CACHE_FILENAME
        assert expected_cache_path.exists(), (
            f"Cache file should exist at: {expected_cache_path}"
        )

        # Verify the slice's note about parent
        # Slice 02-09 says: cache_dir = str(Path(session_root).parent)
        # This is INCORRECT. The correct expression is cache_dir = str(session_root)
        # because session_root IS the session directory.
        incorrect_expression = str(Path(session_root).parent)
        assert cache_dir != incorrect_expression, (
            "The slice incorrectly derives parent of session_root. "
            "cache_dir should be session_root, not its parent.\n"
            f"  cache_dir (correct):     {cache_dir}\n"
            f"  session_root.parent (wrong): {incorrect_expression}"
        )

        print(f"    plan_path:       {plan_path}")
        print(f"    derived cache_dir: {cache_dir}")
        print(f"    cache file exists: ✓ at {expected_cache_path}")
        print(f"    Slice correction: cache_dir = str(session_root) (not .parent) ✓")

        return {
            "scenario": "6. SessionOrchestrator Path Derivation",
            "passed": True,
            "details": {
                "plan_path": str(plan_path),
                "derived_cache_dir": cache_dir,
                "expected_session_root": str(session_root),
                "cache_file_exists": expected_cache_path.exists(),
                "slice_correction": "cache_dir = str(session_root), not .parent",
            },
        }


# ============================================================
# EXAMPLE: Full ContextService Integration Demo
# ============================================================
# This demonstrates how the cache would integrate into the real
# ContextService.get_context() URL-fetching loop.

def demo_context_service_integration(runner: ScenarioRunner) -> Dict[str, Any]:
    """
    Demonstrate how ContextService.get_context() would use WebContentCache
    in its URL-fetching loop.

    The real integration point is in _format_content() / _format_workspace_contents(),
    where URLs are iterated and passed to self._web_scraper.get_content(url).
    """
    session_root = runner.create_session("context-service-demo")
    cache = WebContentCache(cache_dir=session_root)

    # Simulate the URL fetching loop from ContextService._format_workspace_contents()
    urls = [
        "https://example.com/doc1",
        "https://example.com/doc2",
        "https://example.com/doc1",  # Duplicate! Should be cache hit
    ]

    fetch_log: List[str] = []
    results: List[str] = []

    def mock_scraper(url: str) -> str:
        """Simulate IWebScraper.get_content(url)."""
        fetch_log.append(url)
        return f"content for {url}"

    # Integration loop: check cache first, fall back to fetch
    for url in urls:
        cached = cache.get_cached_content(url)
        if cached is not None:
            results.append(cached)
            print(f"    CACHE HIT:   {url} → '{cached}'")
        else:
            content = cache.fetch_and_cache(url, mock_scraper)
            results.append(content)
            print(f"    FETCH:       {url} → '{content}'")

    assert len(fetch_log) == 2, (
        f"Only 2 unique URLs should fetch, got {len(fetch_log)}: {fetch_log}"
    )
    assert results[0] == "content for https://example.com/doc1"
    assert results[1] == "content for https://example.com/doc2"
    assert results[2] == "content for https://example.com/doc1"  # Cache hit!

    print(f"\n    Total URLs processed: {len(urls)}")
    print(f"    Unique fetches: {len(fetch_log)} (1 saved by cache)")
    print(f"    Cache entries on disk: {len(json.loads(Path(session_root, CACHE_FILENAME).read_text()))}")

    return {
        "scenario": "7. ContextService Integration Demo",
        "passed": True,
        "details": {
            "urls_processed": len(urls),
            "unique_fetches": len(fetch_log),
            "cache_hits": len(urls) - len(fetch_log),
            "results": results,
        },
    }


# ============================================================
# ORCHESTRATION
# ============================================================

def run_all_scenarios(runner: ScenarioRunner) -> List[Dict[str, Any]]:
    """Execute all scenarios and return results."""
    results = []
    results.append(runner.scenario_cache_hit())
    results.append(runner.scenario_cache_miss_to_hit())
    results.append(runner.scenario_cache_corruption())
    results.append(runner.scenario_backward_compatibility())
    results.append(runner.scenario_network_failure())
    results.append(runner.scenario_path_derivation())
    results.append(demo_context_service_integration(runner))
    return results


def print_results(results: List[Dict[str, Any]]) -> bool:
    """Display results. Returns True if all passed."""
    all_passed = True
    print(f"\n{'=' * 70}")
    print(f"  Web Content Caching Prototype — Results")
    print(f"{'=' * 70}")

    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"\n  {status}  {r['scenario']}")
        for key, value in r["details"].items():
            print(f"      {key}: {value}")
        if not r["passed"]:
            all_passed = False

    print(f"\n  {'─' * 66}")
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"  {passed}/{total} scenarios passed  •  "
          f"{'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    print(f"{'=' * 70}\n")
    return all_passed


# ============================================================
# MODES
# ============================================================

def verify_mode() -> bool:
    """Non-interactive mode: run all assertions, return success."""
    with ScenarioRunner() as runner:
        results = run_all_scenarios(runner)
        return print_results(results)


def interactive_mode() -> None:
    """Interactive showcase mode with menu-driven scenario selection."""
    print(f"\n{'=' * 70}")
    print(f"  🌐  Web Content Caching Prototype  —  Slice 02-09")
    print(f"{'=' * 70}")
    print(f"""
  This prototype validates the session-level web content caching design.

  Select a scenario to run:
    ┌─────┬─────────────────────────────────────────────────────┐
    │ [1] │ Cache Hit         — Pre-seeded cache, zero fetches  │
    │ [2] │ Cache Miss → Hit  — Fetch once, cache, serve later  │
    │ [3] │ Cache Corruption  — Malformed JSON, graceful fallback│
    │ [4] │ Backward Compat   — No cache_dir, all calls fetch   │
    │ [5] │ Network Failure   — Errors never cached, retry works │
    │ [6] │ Path Derivation   — SessionOrchestrator integration │
    │ [7] │ Full Integration  — ContextService URL-fetching loop │
    │ [a] │ ALL Scenarios     — Run everything                   │
    │ [q] │ Quit              — Exit interactive mode            │
    └─────┴─────────────────────────────────────────────────────┘
  Enter a number, 'a' for all, or 'q' to quit.
""")

    while True:
        try:
            prompt = "\n  Choice: "
            choice = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        with ScenarioRunner() as runner:
            scenario_map = {
                "1": runner.scenario_cache_hit,
                "2": runner.scenario_cache_miss_to_hit,
                "3": runner.scenario_cache_corruption,
                "4": runner.scenario_backward_compatibility,
                "5": runner.scenario_network_failure,
                "6": runner.scenario_path_derivation,
                "7": lambda: demo_context_service_integration(runner),
            }

            if choice == "q":
                print("  Exiting. 👋\n")
                break
            elif choice == "a":
                print(f"\n  {SCENARIO_SEPARATOR}")
                print("  Running ALL scenarios...")
                print(f"  {SCENARIO_SEPARATOR}")
                results = run_all_scenarios(runner)
                print_results(results)
            elif choice in scenario_map:
                print(f"\n  {SCENARIO_SEPARATOR}")
                print(f"  Running scenario {choice}...")
                print(f"  {SCENARIO_SEPARATOR}")
                result = scenario_map[choice]()
                print(f"\n  {'─' * 66}")
                status = "✅" if result["passed"] else "❌"
                print(f"  {status}  {result['scenario']}")
                print(f"{'=' * 70}\n")
            else:
                print(f"  Unknown option: {choice!r}. Try 1-7, 'a', or 'q'.")


# ============================================================
# ENTRY POINT
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Web Content Caching Prototype for Slice 02-09",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run non-interactive verification with assertions",
    )
    args = parser.parse_args()

    if args.verify:
        success = verify_mode()
        sys.exit(0 if success else 1)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()