#!/bin/sh
#
# install-hooks.sh
#
# Installs the post-commit test gate hook and pre-commit hooks
# using the pre-commit framework.
#
# The post-commit hook is defined in .pre-commit-config.yaml with
# `stages: [post-commit]` and installed via `pre-commit install --hook-type post-commit`.
# This avoids manual file copies and core.hooksPath conflicts.
#
# Usage: sh scripts/install-hooks.sh
#

set -e

if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit and post-commit hooks..."

    # Ensure core.hooksPath is not set (pre-commit refuses to install with it)
    if git config --get core.hooksPath > /dev/null 2>&1; then
        echo "  Unsetting core.hooksPath (stale from previous configuration)..."
        git config --unset-all core.hooksPath
    fi

    # Install standard pre-commit hooks and post-commit hook
    pre-commit install
    pre-commit install --hook-type post-commit
    echo "Done! Pre-commit and post-commit hooks are active."
else
    echo "Warning: pre-commit not found. Install it with: pip install pre-commit"
    echo "Cannot install post-commit test gate without pre-commit."
    exit 1
fi

echo ""
echo "Installed hooks:"
ls -la .git/hooks/ | grep -v '\.sample$'
