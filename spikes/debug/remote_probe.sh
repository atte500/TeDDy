#!/bin/bash
set -e

echo "##[group]remote_probe"
echo "--- Environment State ---"
echo "PWD: $(pwd)"
echo "GITHUB_WORKSPACE: $GITHUB_WORKSPACE"
echo "USER: $(whoami)"

echo "--- Directory Structure (Depth 2) ---"
find . -maxdepth 2 -not -path '*/.*'

echo "--- Python/Poetry Environment ---"
poetry env info || echo "Poetry info not available"

echo "--- File Existence Check ---"
# Simulating a check for the file that's "missing" in CI
TARGET_CONFIG="config/settings.yaml"
if [ -f "$TARGET_CONFIG" ]; then
    echo "[OK] Found $TARGET_CONFIG"
    ls -l "$TARGET_CONFIG"
else
    echo "[FAIL] $TARGET_CONFIG NOT FOUND"
fi
echo "##[endgroup]"