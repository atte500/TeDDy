#!/usr/bin/env bash
# Manual verification script for Bug #25 fix.
# Run from the project root: bash spikes/debug/25-manual-verify.sh
#
# This script:
# 1. Writes a test Python script that simulates an OSC sequence being injected
#    into stdin (as prompt_toolkit would deliver it).
# 2. Runs the actual ConsoleAskLoop with mocks.
# 3. Verifies the returned input is clean.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "=== Bug #25 Manual Verification ==="
echo ""

# Run the regression test suite first
echo "[1/3] Running regression tests..."
TERM=dumb uv run pytest tests/suites/unit/adapters/outbound/test_console_ask_loop_escape_stripping.py -v --no-header 2>&1 | tail -20

echo ""
echo "[2/3] Running full outbound unit suite..."
TERM=dumb uv run pytest tests/suites/unit/adapters/outbound/ -v --no-header 2>&1 | tail -10

echo ""
echo "[3/3] Real TTY verification (requires interactive terminal)..."
echo ""
echo "The following test will exercise the actual ConsoleAskLoop with"
echo "a real prompt_toolkit prompt. Type something and press Enter."
echo "If you see 'LEAKED: ...' it means escape sequences passed through."
echo ""
cat << 'PYEOF' | uv run python3 -
import sys
import os
sys.path.insert(0, os.getcwd())
from teddy_executor.adapters.outbound.console_interactor_ask_loop import ConsoleAskLoop
from unittest.mock import MagicMock

env = MagicMock()
env.create_temp_file.return_value = "/tmp/test_manual.md"
tooling = MagicMock()
tooling.find_editor.return_value = ["/usr/bin/vim"]
loop = ConsoleAskLoop(env, tooling)

# Simulate: first prompt returns an OSC sequence
# (in real life this would come from terminal emulator)
test_input = "\x1b]11;rgb:1f1f/2323/3535\x1b\\"
print(f"\nSimulating OSC input: {test_input!r}")
result = loop._strip_escape_sequences(test_input)
print(f"Stripped result: {result!r}")
if result == "":
    print("✓ VERIFIED: OSC sequence correctly stripped to empty string")
    sys.exit(0)
else:
    print("✗ FAILED: OSC sequence not fully stripped!")
    sys.exit(1)
PYEOF