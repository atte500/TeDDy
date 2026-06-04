#!/bin/sh
#
# install-hooks.sh
#
# Configures git to use .githooks/ as the hooks directory and
# reinstalls the pre-commit framework into the new location.
#
# Usage: poetry run python scripts/install-hooks.sh
#   or:  sh scripts/install-hooks.sh
#

set -e

echo "Configuring git hooks path to .githooks/..."
git config core.hooksPath .githooks

if command -v pre-commit &> /dev/null; then
    echo "Reinstalling pre-commit hooks into .githooks/..."
    pre-commit install
    echo "Done! Pre-commit and post-commit hooks are active."
else
    echo "Warning: pre-commit not found. Install it with: pip install pre-commit"
    echo "The post-commit test gate is still active."
fi

echo ""
echo "Hooks directory: $(git config core.hooksPath)"
echo "Installed hooks:"
ls -la .githooks/
