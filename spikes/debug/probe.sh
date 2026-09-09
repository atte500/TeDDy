#!/usr/bin/env bash
# Remote Probe for Regression A (Windows universal hang)
# Measures elapsed time for each step of the pre-request pipeline.
# Run from the repo root (where src/ is accessible).

set -euo pipefail

echo "=== Remote Probe: Context Assembly Hang (Regression A) ==="
echo "Host OS: $(uname -a)"
echo "Python: $(python --version 2>&1)"

# Step 0: Import heavy modules and measure start time
START_TOTAL=$(date +%s%N)

echo ""
echo "--- Step 1: litellm import & validate_config ---"
START=$(date +%s%N)
python -c "
import time
t0 = time.perf_counter()
import litellm
t1 = time.perf_counter()
print(f'  litellm import: {(t1-t0)*1000:.1f}ms')
t0 = time.perf_counter()
litellm.validate_environment(model='gpt-4o')
t1 = time.perf_counter()
print(f'  validate_environment: {(t1-t0)*1000:.1f}ms')
"
END=$(date +%s%N)
echo "  Step 1 total: $(( (END - START) / 1000000 ))ms"

echo ""
echo "--- Step 2: tiktoken import & encoding_for_model ---"
START=$(date +%s%N)
python -c "
import time
t0 = time.perf_counter()
import tiktoken
t1 = time.perf_counter()
print(f'  tiktoken import: {(t1-t0)*1000:.1f}ms')
t0 = time.perf_counter()
enc = tiktoken.encoding_for_model('gpt-4o')
t1 = time.perf_counter()
print(f'  encoding_for_model: {(t1-t0)*1000:.1f}ms')
t0 = time.perf_counter()
enc.encode('Hello world', disallowed_special=())
t1 = time.perf_counter()
print(f'  first encode: {(t1-t0)*1000:.1f}ms')
"
END=$(date +%s%N)
echo "  Step 2 total: $(( (END - START) / 1000000 ))ms"

echo ""
echo "--- Step 3: File I/O (context resolution) ---"
START=$(date +%s%N)
python -c "
import time
import tempfile
from pathlib import Path

# Simulate resolving context files
t0 = time.perf_counter()
tmpdir = tempfile.mkdtemp()
for i in range(20):
    (Path(tmpdir) / f'session-{i:02d}.md').write_text('hello' * 1000)
t1 = time.perf_counter()
print(f'  create 20 small files: {(t1-t0)*1000:.1f}ms')

t0 = time.perf_counter()
for p in Path(tmpdir).iterdir():
    _ = p.read_text()
t1 = time.perf_counter()
print(f'  read 20 small files: {(t1-t0)*1000:.1f}ms')
"
END=$(date +%s%N)
echo "  Step 3 total: $(( (END - START) / 1000000 ))ms"

echo ""
echo "--- Step 4: Web cache file I/O (large file) ---"
START=$(date +%s%N)
python -c "
import json
import time
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as d:
    cache_dir = Path(d)
    # Build cache with 500 empty sentinel entries
    cache = {f'https://example.com/failed-{i:04d}': '' for i in range(500)}
    cache_path = cache_dir / '.web_cache.json'

    t0 = time.perf_counter()
    cache_path.write_text(json.dumps(cache), encoding='utf-8')
    loaded = json.loads(cache_path.read_text(encoding='utf-8'))
    t1 = time.perf_counter()
    print(f'  load/write 500 sentinel entries: {(t1-t0)*1000:.1f}ms')

    t0 = time.perf_counter()
    tmp = cache_dir / '.web_cache.json.tmp'
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
    tmp.replace(cache_path)
    t1 = time.perf_counter()
    print(f'  atomic save 500 entries: {(t1-t0)*1000:.1f}ms')
"
END=$(date +%s%N)
echo "  Step 4 total: $(( (END - START) / 1000000 ))ms"

echo ""
echo "--- Step 5: concurrent.futures ThreadPoolExecutor overhead ---"
START=$(date +%s%N)
python -c "
import concurrent.futures
import time

def dummy(x):
    return x*x

t0 = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    list(ex.map(dummy, range(100)))
t1 = time.perf_counter()
print(f'  executor overhead (100 tasks): {(t1-t0)*1000:.1f}ms')
"
END=$(date +%s%N)
echo "  Step 5 total: $(( (END - START) / 1000000 ))ms"

echo ""
echo "--- Summary ---"
END_TOTAL=$(date +%s%N)
TOTAL_MS=$(( (END_TOTAL - START_TOTAL) / 1000000 ))
echo "Total probe duration: ${TOTAL_MS}ms"
echo ""
echo "=== End Probe ==="