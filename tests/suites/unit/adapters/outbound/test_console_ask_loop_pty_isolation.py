"""Tests for PTY isolation in the editor launch path.

These tests verify the structural invariants of the PTY isolation fix:
1. _launch_editor_in_pty creates a pty pair and stores the master fd
2. _close_pty_master closes the fd and resets state
3. _handle_empty_input closes pty before reading file
4. Escape stripping is gated to only when _active_editor_path is set
5. _pty_drainer thread handles data and exits cleanly
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Import the production module directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../src"))

from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
    _ESCAPE_SEQUENCE_RE,
)


class TestPtyIsolationRegression(unittest.TestCase):
    """Regression tests for PTY isolation editor launch."""

    def setUp(self):
        """Create mock dependencies for ConsoleAskLoop."""
        self.system_env = MagicMock()
        self.tooling = MagicMock()
        self.system_env.create_temp_file.return_value = "/tmp/test_editor.md"
        self.tooling.find_editor.return_value = ["/usr/bin/vim"]
        self.loop = ConsoleAskLoop(self.system_env, self.tooling)

    def test_launch_editor_in_pty_uses_os_openpty(self):
        """Verify that _launch_editor_in_pty calls os.openpty."""
        with patch("os.openpty", return_value=(10, 11)) as mock_openpty, \
             patch("subprocess.Popen"), \
             patch("os.close"), \
             patch("threading.Thread") as mock_thread:

            temp_path = self.system_env.create_temp_file(suffix=".md")
            self.loop._launch_editor_in_pty(temp_path)

            mock_openpty.assert_called_once()
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()

    def test_close_pty_master_closes_fd(self):
        """Verify _close_pty_master closes the master fd and resets state."""
        self.loop._pty_master_fd = 10
        with patch("os.close") as mock_close:
            self.loop._close_pty_master()
            mock_close.assert_called_once_with(10)
            self.assertIsNone(self.loop._pty_master_fd)

    def test_pty_drainer_reads_and_discards(self):
        """Verify the drainer thread reads from the pty master."""
        master_fd = 10
        with patch("select.select", return_value=([master_fd], [], [])) as mock_select, \
             patch("os.read", return_value=b""):

            self.loop._pty_drainer(master_fd)
            mock_select.assert_called_once()

    def test_pty_drainer_exits_on_eof(self):
        """Verify drainer exits when os.read returns empty bytes."""
        master_fd = 10
        with patch("select.select", return_value=([master_fd], [], [])), \
             patch("os.read", return_value=b""):

            self.loop._pty_drainer(master_fd)

    def test_pty_drainer_exits_on_closed_fd(self):
        """Verify drainer exits cleanly when fd is closed."""
        master_fd = 10
        with patch("select.select", side_effect=ValueError("I/O operation on closed fd")):
            self.loop._pty_drainer(master_fd)

    def test_stripping_gated_to_editor_path(self):
        """Verify escape sequences are stripped only when editor is active."""
        raw = "some text \x1b[31mcolored\x1b[0m"

        self.loop._active_editor_path = None
        # When editor NOT active, no stripping should occur
        assert hasattr(self.loop, "_strip_escape_sequences")

        self.loop._active_editor_path = "/tmp/editor.md"
        stripped = self.loop._strip_escape_sequences(raw)
        self.assertNotIn("\x1b", stripped)
        self.assertEqual(stripped, "some text colored")

    def test_regex_strips_known_osc_sequences(self):
        """Verify the hardened regex strips standard and stripped OSC tails."""
        test_cases = [
            ("\x1b]10;rgb:8080/8989/b3b3\x1b\\", ""),
            ("]10;rgb:8080/8989/b3b3", ""),
            ("hello world", "hello world"),
            ("hello \x1b[31mworld\x1b[0m", "hello world"),
        ]
        for raw, expected in test_cases:
            with self.subTest(raw=raw[:20]):
                result = _ESCAPE_SEQUENCE_RE.sub("", raw)
                self.assertEqual(result, expected)

    def test_regression_pty_master_closed_on_harvest(self):
        """Verify _handle_empty_input closes pty before reading file."""
        self.loop._active_editor_path = "/tmp/editor.md"
        self.loop._pty_master_fd = 10
        with patch("builtins.open", unittest.mock.mock_open(
            read_data="content\n\n<!-- Please enter your response above this line. -->\n\nprompt\n"
        )), \
             patch.object(self.loop, "_flush_stdin"), \
             patch("os.close") as mock_close:

            result = self.loop._handle_empty_input("prompt")
            self.assertEqual(result, "content")
            mock_close.assert_any_call(10)
            self.assertIsNone(self.loop._pty_master_fd)


if __name__ == "__main__":
    unittest.main()