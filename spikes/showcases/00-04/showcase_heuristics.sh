#!/bin/bash
set -e

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "Running Unified Context Showcase..."
python3 "$DIR/run_showcase.py"