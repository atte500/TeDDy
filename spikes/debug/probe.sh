#!/usr/bin/env bash
# Remote probe: reproduce the missing quit-key interrupt notice on Windows and
# verify the cross-platform SIGINT self-delivery candidate.
set -euo pipefail

mkdir -p spikes/debug
cat > spikes/debug/probe_output.txt <<EOF
=== Probe Metadata ===
OS: $(uname -a)
Python: $(python --version 2>&1)
Platform: $(python -c 'import sys; print(sys.platform)')

=== Production vs Replica MRE ===
EOF

uv run python spikes/debug/windows-quit-notice-suppression/01-quit-notice-mre.py \
  >> spikes/debug/probe_output.txt 2>&1 || true