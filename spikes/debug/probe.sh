#!/usr/bin/env bash
# Remote probe: measure cold-start suite durations and repeat the exact CI
# command to catch the intermittent Windows worker crash.
#
# On a healthy windows-latest runner the crashing tests finish under two
# seconds, so the stall that kills a worker needs a cold or contended host.
# The previous probe warmed every cache before its full-suite runs, so the
# first measurement here is deliberately the first pytest invocation of the
# job. It clears CI because tests/conftest.py forces a 15 second budget
# whenever CI is true, and it uses a 120 second cap as a hang safety net.
# Three repetitions of the unmodified CI command follow, so the intermittent
# crash has three independent chances to appear.
set -uo pipefail

OUT="spikes/debug/probe_output.txt"

mkdir -p spikes/debug

{
  echo "=== CI cold-start and crash reproduction probe ==="
  echo "uname: $(uname -s 2>/dev/null || echo unknown)"
  echo "python: $(uv run python --version 2>&1)"
  echo "cpu_count: $(uv run python -c 'import os; print(os.cpu_count())' 2>&1)"
  echo "CI: ${CI:-unset}"

  echo ""
  echo "=== 1. Cold full-suite durations (CI cleared, 120s cap) $(date -u +%H:%M:%S) ==="
  START=$(date +%s)
  CI= uv run pytest --timeout=120 --durations=40 -q 2>&1 | tail -60
  echo "cold_full_suite_wall_seconds=$(( $(date +%s) - START ))"

  for RUN in A B C; do
    echo ""
    echo "=== 2${RUN}. Exact CI command, run ${RUN} $(date -u +%H:%M:%S) ==="
    START=$(date +%s)
    uv run pytest -q 2>&1 | tail -25
    echo "run_${RUN}_wall_seconds=$(( $(date +%s) - START ))"
  done

  echo ""
  echo "=== done $(date -u +%H:%M:%S) ==="
} 2>&1 | tee "$OUT"
