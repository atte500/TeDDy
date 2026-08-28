#!/usr/bin/env bash
set -euo pipefail

echo "=== Remote Probe: Verify Real Fix for Windows CI RecursionError ==="
echo "Running the real test file (with fix) on Windows to verify no RecursionError..."
echo ""

# Run the real test file with verbose traceback
uv run pytest tests/suites/unit/adapters/outbound/test_console_ask_loop_stdin_flush.py::TestWindowsStdinFlush::test_flush_stdin_uses_msvcrt_when_termios_missing -v --tb=long --no-header 2>&1 || true

echo ""
echo "=== Probe Complete ==="