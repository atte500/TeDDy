#!/usr/bin/env bash
set -euo pipefail

echo "::group::Remote Probe: Git Detection Windows Bug"
echo "Running on: $(uname -s)"

# Run the Python probe script
poetry run python spikes/debug/12-git-detection-rpp.py

echo "::endgroup::"