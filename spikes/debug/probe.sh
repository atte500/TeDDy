#!/usr/bin/env bash
# Remote probe: cross-platform SIGINT delivery latency.
# Writes the artifact at spikes/debug/probe_output.txt and mirrors it to stdout
# so the Ubuntu job log carries the same rows the Windows artifact carries.
set -uo pipefail

OUT="spikes/debug/probe_output.txt"
mkdir -p spikes/debug

{
  echo "=== SIGINT delivery latency probe ==="
  echo "uname: $(uname -s 2>/dev/null || echo unknown)"
  echo "python: $(uv run python --version 2>&1)"
  echo "---"
  uv run python spikes/debug/quit-key-interrupt-latency/02-cross-platform-sigint-delivery-probe.py
  echo "probe_exit=$?"
} 2>&1 | tee "$OUT"