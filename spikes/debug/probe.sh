#!/usr/bin/env bash
set -euo pipefail

echo "Probe running on $(uname -a)"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version 2>&1 || echo 'N/A')"
echo "Path: $PATH"

# Save output to a file for artifact upload
mkdir -p spikes/debug/output
cat > spikes/debug/probe_output.txt <<EOF
=== Probe Result ===
OS: $(uname -s)
Python: $(python --version 2>&1)
Git: $(git --version 2>&1)
EOF
echo "Probe output saved to spikes/debug/probe_output.txt"