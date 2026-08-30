#!/usr/bin/env bash
set -euo pipefail

echo "=== PROBE: Vim Color Capability Check ==="

echo "OS: $(uname -s)"
echo "Term: ${TERM:-unset}"

# Install vim if not available
if ! command -v vim &>/dev/null; then
    echo "Vim not found. Installing..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq vim 2>&1 | tail -3
    elif command -v brew &>/dev/null; then
        brew install vim 2>&1 | tail -3
    fi
fi
echo "Vim version: $(vim --version 2>&1 | head -1)"

# Create test diff file
cat > /tmp/probe_test_diff.diff << 'EOF'
--- a/test.txt (original)
+++ b/test.txt (proposed)
@@ -1,3 +1,4 @@
 def old_function():
-    return old_value
+    return new_value

+def new_function():
+    return 42
EOF

# Test 1: Vim diagnostics inside pseudo-terminal (script)
echo ""
echo "=== Test 1: Vim diagnostics inside script (pseudo-terminal) ==="

# Use -u NONE to prevent vimrc interference, -i NONE to prevent viminfo
if [ "$(uname -s)" = "Linux" ]; then
    script -q -c "vim -u NONE -i NONE -c 'redir! > /tmp/vim_diag1.txt' \
        -c 'echo \"t_Co: \" . &t_Co' \
        -c 'echo \"term: \" . &term' \
        -c 'echo \"syntax_on: \" . exists(\"g:syntax_on\")' \
        -c 'echo \"filetype: \" . &filetype' \
        -c 'echo \"background: \" . &background' \
        -c 'echo \"termguicolors: \" . &termguicolors' \
        -c 'echo \"has_terminfo: \" . has(\"terminfo\")' \
        -c 'redir END' \
        -c 'qall!' /tmp/probe_test_diff.diff" /dev/null 2>/dev/null || true
else
    # macOS: script expects command as positional argument
    script -q /dev/null vim -u NONE -i NONE \
        -c 'redir! > /tmp/vim_diag1.txt' \
        -c 'echo "t_Co: " . &t_Co' \
        -c 'echo "term: " . &term' \
        -c 'echo "syntax_on: " . exists("g:syntax_on")' \
        -c 'echo "filetype: " . &filetype' \
        -c 'echo "background: " . &background' \
        -c 'echo "termguicolors: " . &termguicolors' \
        -c 'echo "has_terminfo: " . has("terminfo")' \
        -c 'redir END' \
        -c 'qall!' /tmp/probe_test_diff.diff 2>/dev/null || true
fi

if [ -f /tmp/vim_diag1.txt ]; then
    cat /tmp/vim_diag1.txt
else
    echo "WARNING: No Test 1 output file created."
fi

# Test 2: Direct vim color test (baseline without pseudo-terminal)
echo ""
echo "=== Test 2: Vim diagnostics without pseudo-terminal (baseline) ==="
vim -u NONE -i NONE -c 'redir! > /tmp/vim_diag2.txt' \
    -c 'echo "t_Co: " . &t_Co' \
    -c 'echo "term: " . &term' \
    -c 'echo "syntax_on: " . exists("g:syntax_on")' \
    -c 'echo "filetype: " . &filetype' \
    -c 'echo "has_terminfo: " . has("terminfo")' \
    -c 'redir END' \
    -c 'qall!' /tmp/probe_test_diff.diff 2>/dev/null || true

if [ -f /tmp/vim_diag2.txt ]; then
    cat /tmp/vim_diag2.txt
else
    echo "WARNING: No Test 2 output file created."
fi

# Test 3: Vim syntax highlight groups (check if colors are assigned)
echo ""
echo "=== Test 3: Vim highlight groups with diff syntax ==="
vim -u NONE -i NONE -c 'syntax on' -c 'set filetype=diff' \
    -c 'redir! > /tmp/vim_diag3.txt' \
    -c 'highlight' \
    -c 'redir END' \
    -c 'qall!' /tmp/probe_test_diff.diff 2>/dev/null || true

if [ -f /tmp/vim_diag3.txt ]; then
    COLOR_GROUPS=$(grep -c 'ctermfg\|guifg' /tmp/vim_diag3.txt 2>/dev/null || echo "0")
    echo "Highlight groups with color definitions: ${COLOR_GROUPS}"
    echo ""
    echo "Diff-specific highlight groups:"
    grep -E '(DiffAdd|DiffDelete|DiffChange|DiffText)' /tmp/vim_diag3.txt | head -10
    echo ""
    echo "Sample common groups:"
    grep -E '(Comment|Constant|Identifier|Statement|String)' /tmp/vim_diag3.txt | head -10
else
    echo "WARNING: No Test 3 output file created."
fi

# Write results to CI-expected output path
cat > /tmp/probe_output.txt << 'EOF'
All tests executed. See individual diagnostic files above.
EOF

echo ""
echo "=== PROBE COMPLETE ==="
echo "Diagnostic files:"
ls -la /tmp/vim_diag1.txt /tmp/vim_diag2.txt /tmp/vim_diag3.txt 2>/dev/null || echo "(some files missing)"