#!/usr/bin/env bash
# Case File 51 remote probe entry point (consumed by .github/workflows/debug.yml).
# Runs the comparative performance probe and persists output for artifact upload.
set -uo pipefail

OUT="$(dirname "$0")/probe_output.txt"

echo "=== Case File 51 perf probe ($(uname -s 2>/dev/null || echo unknown)) ==="
uv run python spikes/debug/51-perf-probe.py 2>&1 | tee "$OUT"
exit "${PIPESTATUS[0]}"