#!/usr/bin/env bash
# Remote Probe Test Script
set -euo pipefail

echo "=== REMOTE PROBE START ==="
echo "Host: $(uname -a)"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Git commit: $(git rev-parse HEAD 2>/dev/null || echo 'not a git repo')"
echo "Git branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'N/A')"
echo "Python version: $(python3 --version 2>/dev/null || echo 'python3 not found')"
echo "Current dir: $(pwd)"
echo "Files in spikes/debug/: $(ls -la spikes/debug/ 2>/dev/null || echo 'dir not found')"
echo "=== REMOTE PROBE END ==="
