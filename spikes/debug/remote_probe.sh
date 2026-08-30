#!/usr/bin/env bash
set -euo pipefail

echo "=== REMOTE PROBE: Vim inside Textual suspend context ==="

# Install vim if not available
if ! command -v vim &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq vim 2>&1 | tail -3
    elif command -v brew &>/dev/null; then
        brew install vim 2>&1 | tail -3
    else
        echo "ERROR: cannot install vim (no apt-get or brew)"
        exit 1
    fi
fi

echo "vim version: $(vim --version | head -2)"

# Create the probe Python script as a heredoc
cat > /tmp/probe_suspend.py << 'PYEOF'
import sys
import os
import subprocess
import tempfile

# Minimal Textual app to reproduce suspend context
from textual.app import App

class ProbeApp(App):
    def on_mount(self):
        self.suspend_and_probe()

    def suspend_and_probe(self):
        diff_content = """--- a/test.txt (original)
+++ b/test.txt (proposed)
@@ -1,0 +1,2 @@
+def new_function():
+    return 42
"""

        # Write diff file
        diff_path = "/tmp/probe_diff.diff"
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff_content)

        # Diagnostic commands for vim
        diag_cmds = [
            "verbose set syntax?",
            "set filetype?",
            "echo &t_Co",
            "echo &term",
            "echo &background",
            "echo has('syntax')",
            "echo &termguicolors",
            "colorscheme",
            "echo g:colors_name",
            "q!",
        ]
        cmd = " | ".join(diag_cmds)
        vim_cmd = f"vim -c 'silent! {cmd}' {diff_path}"

        with self.suspend():
            try:
                # Use script to get a pseudo-terminal for accurate vim behavior
                if sys.platform == "linux":
                    script_cmd = ["script", "-q", "-c", vim_cmd, "/dev/null"]
                else:  # macOS
                    script_cmd = ["script", "-q", vim_cmd, "/dev/null"]
                result = subprocess.run(
                    script_cmd,
                    capture_output=True,
                    timeout=10,
                )
                # vim outputs diagnostics to stderr (because we captured)
                output = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                output = "TIMEOUT: vim did not exit within 10 seconds"
            except Exception as e:
                output = f"ERROR: {e}"

            # Write result to a known file so the outer shell can read it
            with open("/tmp/probe_result.txt", "w", encoding="utf-8") as f:
                f.write(output)

        self.exit()

if __name__ == "__main__":
    app = ProbeApp()
    app.run()
PYEOF

# Run the probe (needs a pseudo-terminal to simulate real TUI environment)
echo "=== Running probe script (may take a few seconds) ==="
python3 /tmp/probe_suspend.py 2>&1 || echo "Probe script failed (check stderr above)"

# Read and print the result
echo ""
echo "=== PROBE RESULT ==="
if [ -f /tmp/probe_result.txt ]; then
    cat /tmp/probe_result.txt
else
    echo "No result file found."
fi
echo "=== END PROBE RESULT ==="