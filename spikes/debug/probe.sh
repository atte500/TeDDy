#!/usr/bin/env bash
# Remote probe: measure test durations on the CI host against the per-test
# budget, and observe the intermittent worker crash directly.
#
# Hypothesis: subprocess-heavy acceptance and integration tests exceed the
# 15 second CI budget on windows-latest, so the pytest-timeout thread timer
# calls os._exit(1) and xdist reports "node down". Each serial measurement runs
# in its own invocation, because the 30 second per-test markers on two of the
# targets override the command-line value and a shared invocation would hide
# the other durations. The full-suite runs use the exact CI command so the
# intermittent crash can occur on the real host.
set -uo pipefail

OUT="spikes/debug/probe_output.txt"
T1="tests/suites/acceptance/test_session_management.py::test_teddy_resume_continuous_loop"
T2="tests/suites/acceptance/test_workspace_start_pull.py::test_start_fast_forwards_a_behind_workspace"
T3="tests/suites/integration/core/services/test_session_orchestration_integration.py::test_history_log_append_mode"

mkdir -p spikes/debug

{
  echo "=== CI duration probe ==="
  echo "uname: $(uname -s 2>/dev/null || echo unknown)"
  echo "python: $(uv run python --version 2>&1)"
  echo "cpu_count: $(uv run python -c 'import os; print(os.cpu_count())' 2>&1)"
  echo "CI: ${CI:-unset}"

  echo ""
  echo "=== 1. Process spawn cost (10 git calls) $(date -u +%H:%M:%S) ==="
  uv run python -c "import subprocess,time;t=time.perf_counter();[subprocess.run(['git','rev-parse','--git-dir'],capture_output=True) for _ in range(10)];print('ten_git_calls_seconds=%.2f' % (time.perf_counter()-t))"

  echo ""
  echo "=== 2. Serial per-test durations (CI cleared) $(date -u +%H:%M:%S) ==="
  for T in "$T1" "$T2" "$T3"; do
    echo "---- $T ----"
    CI= uv run pytest "$T" -n0 --timeout=120 --durations=0 -q 2>&1 | tail -22
  done

  echo ""
  echo "=== 3. Session-management module under xdist, 15s budget $(date -u +%H:%M:%S) ==="
  CI=true uv run pytest tests/suites/acceptance/test_session_management.py -n auto --timeout=15 --durations=0 2>&1 | tail -60

  echo ""
  echo "=== 4. Full suite run A with the real CI command $(date -u +%H:%M:%S) ==="
  uv run pytest -q 2>&1 | tail -35

  echo ""
  echo "=== 5. Full suite run B with the real CI command $(date -u +%H:%M:%S) ==="
  uv run pytest -q 2>&1 | tail -35

  echo ""
  echo "=== done $(date -u +%H:%M:%S) ==="
} 2>&1 | tee "$OUT"
