#!/bin/sh
#
# install-hooks.sh
#
# Installs the post-commit test gate hook into .git/hooks/ and
# ensures pre-commit framework hooks are installed.
#
# The post-commit hook is committed at .githooks/post-commit and
# is copied to .git/hooks/post-commit at install time. This keeps
# the hook version-controlled while avoiding core.hooksPath conflicts
# with the pre-commit framework.
#
# Usage: sh scripts/install-hooks.sh
#

set -e

HOOKS_SOURCE=".githooks/post-commit"
HOOKS_TARGET=".git/hooks/post-commit"

echo "Installing post-commit test gate..."
mkdir -p .git/hooks
cp "$HOOKS_SOURCE" "$HOOKS_TARGET"
chmod +x "$HOOKS_TARGET"
echo "  -> $HOOKS_TARGET"

if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit hooks..."

    # Ensure core.hooksPath is not set (pre-commit refuses to install with it)
    if git config --get core.hooksPath > /dev/null 2>&1; then
        echo "  Unsetting core.hooksPath (stale from previous configuration)..."
        git config --unset-all core.hooksPath
    fi

    pre-commit install
    echo "Done! Pre-commit and post-commit hooks are active."
else
    echo "Warning: pre-commit not found. Install it with: pip install pre-commit"
    echo "The post-commit test gate is still active."
fi

echo ""
echo "Installed hooks:"
ls -la .git/hooks/ | grep -v '\.sample$'
