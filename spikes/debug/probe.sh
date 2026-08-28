#!/usr/bin/env bash
set -euo pipefail

echo "=== Remote Probe: Trigger Windows CI RecursionError ==="
echo "Running the failing test on Windows to reproduce the RecursionError..."
echo ""

# Run the specific failing test with verbose traceback
uv run pytest tests/suites/unit/adapters/outbound/test_console_ask_loop_stdin_flush.py::TestWindowsStdinFlush::test_flush_stdin_uses_msvcrt_when_termios_missing -v --tb=long --no-header 2>&1 || true

echo ""
echo "=== Probe Complete ==="