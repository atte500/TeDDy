#!/usr/bin/env python3
"""
MRE for Bug #36: TUI Vim Grey Colors

Run this script to reproduce the issue and capture vim's state diagnostics
INSIDE the Textual suspend context. This is the ONLY way to get vim's
internal state at the exact moment syntax highlighting fails.

Usage:
    uv run python spikes/debug/36-mre-user.py

This will:
1. Create a minimal Textual app
2. Generate a test .diff file (same format as the TUI plan reviewer)
3. Inside app.suspend(), run vim with diagnostic commands
4. Capture vim's t_Co, syntax status, filetype, colors_name, etc.
5. Print the diagnostics to stdout

Output shows exactly what vim 'sees' when launched inside suspend.
"""

import os
import sys
import tempfile


def main():
    # Create test diff file in a temporary directory
    test_dir = tempfile.mkdtemp(prefix="teddy_bug36_")
    diff_path = os.path.join(test_dir, "test.diff")
    diff_content = (
        "--- a/test.txt (original)\n"
        "+++ b/test.txt (proposed)\n"
        "@@ -1,3 +1,4 @@\n"
        " def old_function():\n"
        "-    return old_value\n"
        "+    return new_value\n"
        " \n"
        "+def new_function():\n"
        "+    return 42\n"
    )
    with open(diff_path, "w", encoding="utf-8") as f:
        f.write(diff_content)

    # Create vim diagnostic script that writes state to a file
    vim_output_path = os.path.join(test_dir, "vim_diag_output.txt")
    vim_diag_path = os.path.join(test_dir, "vim_diag.vim")
    vim_script = f"""
" Vim diagnostic script for Bug #36
redir! > {vim_output_path}
  echo '=== Vim State Diagnostics ==='
  echo 't_Co: ' . &t_Co
  echo 'term: ' . &term
  echo 'syntax_on: ' . (exists('g:syntax_on') ? '1' : '0')
  echo 'filetype: ' . &filetype
  echo 'background: ' . &background
  echo 'termguicolors: ' . &termguicolors
  echo 'has("syntax"): ' . has('syntax')
  echo 'has("terminfo"): ' . has('terminfo')
  echo 'has("gui_running"): ' . has('gui_running')
  echo 'has("ttyin"): ' . has('ttyin')
  echo 'has("ttyout"): ' . has('ttyout')
  echo 'colors_name: ' . (exists('g:colors_name') ? g:colors_name : 'NOT SET')
  echo 'verbose syntax:'
  verbose set syntax?
  echo 'verbose filetype:'
  set filetype?
  echo '=== Highlight Groups ==='
  highlight
  echo '=== End Diagnostics ==='
redir END
qall!
"""
    with open(vim_diag_path, "w", encoding="utf-8") as f:
        f.write(vim_script)

    # Print environment info
    print("=" * 60)
    print("Bug #36: Vim Color Diagnostic MRE")
    print("=" * 60)
    print(f"Test diff: {diff_path}")
    print(f"Vim diag script: {vim_diag_path}")
    print(f"TERM: {os.environ.get('TERM', 'UNSET')}")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()

    # Import Textual inside the function (lazy import to avoid import-order issues)
    try:
        from textual.app import App
    except ImportError as e:
        print(f"ERROR: Cannot import Textual: {e}")
        print("Make sure to run with: uv run python spikes/debug/36-mre-user.py")
        sys.exit(1)

    class ProbeApp(App):
        """Minimal Textual app that probes vim state inside suspend."""

        def on_mount(self):
            self.run_probe()

        def run_probe(self):
            print("Entering suspend() context...")
            with self.suspend():
                print("  Inside suspend(). Running vim with diagnostics...")
                print(f"  stdin.isatty(): {sys.stdin.isatty()}")
                print(f"  TERM: {os.environ.get('TERM', 'UNSET')}")
                print(f"  Vim will write diagnostics to: {vim_output_path}")
                print()

                # Run vim directly (uses inherited TTY from suspend context)
                import subprocess  # nosec B404

                result = subprocess.run(
                    ["vim", "-u", "NONE", "-S", vim_diag_path, diff_path],
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    timeout=30,
                )
                print(f"  vim exit code: {result.returncode}")

            print()
            print("Exited suspend() context.")
            self.exit()

    print("Starting Textual app...")
    print("(vim will open automatically inside the suspend context)")
    print()

    app = ProbeApp()
    try:
        app.run()
    except Exception as e:
        print(f"ERROR running Textual app: {e}")

    # Read and display vim diagnostic output
    print()
    print("=" * 60)
    print("VIM DIAGNOSTIC OUTPUT")
    print("=" * 60)
    if os.path.exists(vim_output_path):
        with open(vim_output_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("ERROR: Diagnostic output file not found!")
        print(f"Expected at: {vim_output_path}")
        print("This could mean vim did not execute the diagnostic script properly.")

    # Cleanup temp files
    for f_path in [diff_path, vim_diag_path]:
        try:
            os.unlink(f_path)
        except OSError:
            pass
    try:
        os.rmdir(test_dir)
    except OSError:
        pass

    print("=" * 60)
    print("Diagnostic complete. Share the VIM DIAGNOSTIC OUTPUT above")
    print("with the developer to help diagnose the grey colors issue.")
    print("=" * 60)


if __name__ == "__main__":
    main()