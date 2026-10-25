#!/usr/bin/env bash
# Remote probe: measure test durations on the CI host against the 15 second
# per-test budget.
#
# The hypothesis is that subprocess-heavy tests exceed the 15 second CI budget
# on the windows-latest runner, so the pytest-timeout thread timer calls
# os._exit(1) and xdist reports "node down". The serial runs use a generous
# 120 second cap so a genuine hang still surfaces a stack dump, while the
# xdist runs measure the contended cost under the real budget.
set -uo pipefail

OUT="spikes/debug/probe_output.txt"
CRASH_TESTS="tests/suites/acceptance/test_session_management.py::test_teddy_resume_continuous_loop tests/suites/acceptance/test_workspace_start_pull.py::test_start_fast_forwards_a_behind_workspace tests/suites/integration/core/services/test_session_orchestration_integration.py::test_history_log_append_mode"

mkdir -p spikes/debug

{
  echo "=== CI duration probe ==="
  echo "uname: $(uname -s 2>/dev/null || echo unknown)"
  echo "python: $(uv run python --version 2>&1)"
  echo "cpu_count: $(uv run python -c 'import os; print(os.cpu_count())' 2>&1)"
  echo "CI: ${CI:-unset}"

  echo ""
  echo "=== 1. Process spawn cost (10 git calls) ==="
  uv run python -c "import subprocess,time;t=time.perf_counter();[subprocess.run(['git','rev-parse','--git-dir'],capture_output=True) for _ in range(10)];print('ten_git_calls_seconds=%.2f' % (time.perf_counter()-t))"

  echo ""
  echo "=== 2. Uncontended durations (CI cleared, 120s cap, serial) ==="
  START=$(date +%s)
  CI= uv run pytest $CRASH_TESTS -n0 --timeout=120 --durations=0 -q 2>&1 | tail -40
  echo "serial_wall_seconds=$(( $(date +%s) - START ))"

  echo ""
  echo "=== 3. Session-management module under xdist with the 15s budget ==="
  START=$(date +%s)
  CI=true uv run pytest tests/suites/acceptance/test_session_management.py -n auto --timeout=15 --durations=0 2>&1 | tail -70
  echo "module_wall_seconds=$(( $(date +%s) - START ))"

  echo ""
  echo "=== 4. Sibling crash modules under xdist with the 15s budget ==="
  START=$(date +%s)
  CI=true uv run pytest tests/suites/acceptance/test_workspace_start_pull.py tests/suites/integration/core/services/test_session_orchestration_integration.py -n auto --timeout=15 --durations=0 2>&1 | tail -70
  echo "siblings_wall_seconds=$(( $(date +%s) - START ))"

  echo ""
  echo "=== done ==="
} 2>&1 | tee "$OUT"
