#!/bin/bash
set -euo pipefail

echo "=== Windows Interactive Probe ==="
echo "Platform: $(uname -o 2>/dev/null || echo 'non-Windows')"

# Test 1: Run the exact failing command and capture all details
echo ""
echo "--- Test 1: Direct execution of 'cmd /c \"set /p test_var=\"' ---"
python3 -c "
import subprocess, sys
proc = subprocess.Popen(
    'cmd /c \"set /p test_var=\"',
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.DEVNULL,
    text=True,
    cwd='.',
)
stdout, stderr = proc.communicate(timeout=5)
print(f'Return code: {proc.returncode}')
print(f'stdout: {stdout!r}')
print(f'stderr: {stderr!r}')
patterns = [
    'Input required',
    'Unexpected EOF',
    'cannot read input',
    'EOFError',
    'input(',
    'is not a TTY',
    'not a tty',
    'stdin is not a terminal',
    'read error',
    'Input/output error',
    'Inappropriate ioctl',
    'cannot read input',
]
matched = [p for p in patterns if p in stderr or p in stdout]
print(f'Patterns matched in stderr or stdout: {matched}')
" 2>&1 || true

# Test 2: Combined stdout+stderr analysis
echo ""
echo "--- Test 2: stdout+stderr combined analysis ---"
python3 -c "
import subprocess
proc = subprocess.Popen(
    'cmd /c \"set /p test_var=\"',
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    text=True,
)
combined, _ = proc.communicate(timeout=5)
print(f'Return code: {proc.returncode}')
print(f'Combined output: {combined!r}')
"

# Test 3: Command string analysis for interactive indicators
echo ""
echo "--- Test 3: Command string analysis ---"
python3 -c "
import re
command = 'cmd /c \"set /p test_var=\"'
interactive_patterns = [
    r'set /p',
    r'choice',
    r'pause',
    r'input',
    r'read -p',
    r'getpass',
    r'--interactive',
    r'-i',
]
matched = [p for p in interactive_patterns if re.search(p, command, re.IGNORECASE)]
print(f'Command: {command}')
print(f'Interactive patterns matched: {matched}')
"

echo ""
echo "=== Probe Complete ==="