#!/usr/bin/env python3
"""
MRE for Regression B (Web Cache Bloat).
Demonstrates that saving/loading a large .web_cache.json with many empty-string
entries becomes a measurable delay. Run from project root.
"""
import json
import time
import tempfile
from pathlib import Path

# Number of empty sentinel entries to simulate
ENTRY_COUNT = 500  # Simulates ~500 failed URL fetches over a session

def simulate_cache_entry(n: int) -> str:
    return f"https://example.com/failed-url-{n:04d}"

def measure_load(cache_path: Path, cache: dict) -> float:
    """Measure time to read and deserialize the cache."""
    start = time.perf_counter()
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    loaded = json.loads(cache_path.read_text(encoding="utf-8"))
    elapsed = time.perf_counter() - start
    return elapsed

def measure_save(cache_dir: Path, cache: dict) -> float:
    """Measure time to atomically write cache (temp + rename)."""
    start = time.perf_counter()
    target = cache_dir / ".web_cache.json"
    tmp = cache_dir / ".web_cache.json.tmp"
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    elapsed = time.perf_counter() - start
    return elapsed

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        # Build cache with many empty sentinel entries
        cache: dict = {}
        for i in range(ENTRY_COUNT):
            url = simulate_cache_entry(i)
            cache[url] = ""  # Empty string sentinel for failed fetch

        # Measure load (combined write + read)
        cache_path = cache_dir / ".web_cache.json"
        load_time = measure_load(cache_path, cache)
        print(f"Cache size: {cache_path.stat().st_size} bytes")
        print(f"Load (write+read) for {ENTRY_COUNT} entries: {load_time*1000:.2f}ms")

        # Measure save (atomic write)
        save_time = measure_save(cache_dir, cache)
        print(f"Save (atomic write) for {ENTRY_COUNT} entries: {save_time*1000:.2f}ms")

        # Also test with 2000 entries to simulate a heavy session
        big_cache = {}
        for i in range(2000):
            url = simulate_cache_entry(i)
            big_cache[url] = ""
        load_time_big = measure_load(cache_path, big_cache)
        print(f"\n2000 entries load: {load_time_big*1000:.2f}ms")
        save_time_big = measure_save(cache_dir, big_cache)
        print(f"2000 entries save: {save_time_big*1000:.2f}ms")

if __name__ == "__main__":
    main()