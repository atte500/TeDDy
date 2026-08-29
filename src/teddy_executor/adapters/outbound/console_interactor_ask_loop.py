from __future__ import annotations

import logging
import os
import re
import sys
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import prompt as ptk_prompt

if TYPE_CHECKING:
    from teddy_executor.adapters.outbound.console_tooling import (
        ConsoleToolingHelper,
    )
    from teddy_executor.core.ports.outbound.system_environment import (
        ISystemEnvironment,
    )

# Regex to match ANSI SGR codes and OSC sequences, including partially
# stripped OSC color-palette tails whose leading ESC byte was consumed by
# terminal processing (e.g., `]10;rgb:8080/8989/b3b3`).
#   - ANSI SGR: ESC [ <params> m (e.g., \x1b[31m) or any final byte [a-zA-Z]
#   - OSC (full): ESC ] ... ST (ESC \ or BEL \x07)
#   - OSC (stripped tail): `]10;[<params>;]rgb:<hex...>` — narrowed to the
#     `rgb:` palette syntax emitted by terminals when restoring dynamic colors,
#     so ordinary text like `]1, 2, 3` is never stripped.
_ESCAPE_SEQUENCE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]"
    r"|\x1b\][^\x1b]*(?:\x1b\\|\x07)"
    r"|(?![\d;,])]10;(?:\d+;)?rgb:[\da-fA-F/]+(?::$|[a-zA-Z])?(?:\x1b\\|\x07)?"
)

logger = logging.getLogger(__name__)

# Set of known CLI (terminal) editors. GUI editors (code, sublime, cursor, etc.)
# will default to the asynchronous background launch pattern.
_CLI_EDITORS: set[str] = {
    "vim",
    "nvim",
    "vi",
    "nano",
    "micro",
    "emacs",
    "pico",
    "helix",
    "hx",
    "kak",
}


class ConsoleAskLoop:
    """Handles the interactive loop for capturing user response via terminal or editor."""

    def __init__(self, system_env: ISystemEnvironment, tooling: ConsoleToolingHelper):
        self._system_env = system_env
        self._tooling = tooling
        self._history = InMemoryHistory()
        self._active_editor_path: Optional[str] = None

    @staticmethod
    def _is_cli_editor(editor_cmd: Optional[list[str]]) -> bool:
        """Return True if the resolved editor command is a known terminal (CLI) editor.

        Uses the basename of the executable to classify. Returns False for
        unknown editors, empty commands, or None (default to GUI/background pattern).
        """
        if not editor_cmd:
            return False
        basename = os.path.basename(editor_cmd[0])
        return basename in _CLI_EDITORS

    def _is_tty(self) -> bool:
        """Check if stdin is a real TTY (vs pipe/test runner)."""
        return sys.stdin.isatty()

    def _flush_stdin(self) -> None:
        """Flush stale escape sequences from the TTY input buffer.

        After an editor process exits, the terminal emulator may have written
        escape sequences into the shared stdin buffer. Flushing before the next
        prompt prevents them from being captured as user input.

        Supports both POSIX (termios.tcflush) and Windows (msvcrt.kbhit/getwch).
        Falls back to no-op if both are unavailable.
        """
        if not self._is_tty():
            return
        try:
            import termios  # noqa: PLC0415

            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except ImportError:
            # Windows path: msvcrt is only available on Windows.
            # Use an inner try/except so that if msvcrt itself is unavailable
            # (e.g., running on non-Windows or patched __import__ during tests),
            # the failure is silently caught rather than propagating.
            try:
                import msvcrt  # noqa: PLC0415

                while msvcrt.kbhit():
                    msvcrt.getwch()  # drain one character (discarded)
            except ImportError:
                pass
        except Exception:  # nosec B110
            pass

    def _strip_escape_sequences(self, text: str) -> str:
        """Remove ANSI escape sequences and OSC control sequences from text."""
        return _ESCAPE_SEQUENCE_RE.sub("", text)

    def _pt_prompt(self, prompt_text: str) -> str:
        """Prompt the user using prompt_toolkit (TTY) or input() (non-TTY/pipe)."""
        if not self._is_tty():
            try:
                return input(prompt_text)
            except EOFError:
                return ""
        try:
            return ptk_prompt(prompt_text, history=self._history)
        except (EOFError, KeyboardInterrupt):
            return ""

    def run(self, prompt: str) -> str:
        """Orchestrates the interactive loop for capturing user response.

        The loop runs until the user provides a non-empty response. Typing 'e'
        opens an external editor synchronously. After the editor exits, the
        file content is read and returned if non-empty.
        """
        while True:
            if self._active_editor_path:
                prompt_text = (
                    "Editor opened. Terminal reply or [Enter] to confirm editor › "
                )
            else:
                prompt_text = "Response (type 'e' for editor) › "
            raw_input = self._pt_prompt(prompt_text).strip()
            # Gate stripping: only strip when editor is active
            # (prevents antipattern of stripping intentional escape sequences
            # from direct user input)
            if self._active_editor_path:
                user_input = self._strip_escape_sequences(raw_input)
            else:
                user_input = raw_input

            if user_input.lower() == "e":
                content = self._launch_editor_background(prompt)
                if content:
                    return content
                # FIX: flush stale terminal escape sequences immediately after
                # the editor spawn, BEFORE the next prompt reads from stdin.
                self._flush_stdin()
                # Empty editor content: back to normal prompt
                continue

            if user_input:
                return user_input

            response = self._handle_empty_input(prompt)
            if response is not None:
                return response

    def _launch_editor_background(self, prompt: str) -> str:
        """Opens an external editor in the background and returns the harvested content.

        Creates a temp file with initial content (marker + prompt), spawns the editor
        via subprocess.Popen with TTY inheritance, and stores the path for later harvest.
        On subsequent calls, reuses the stored persistent file and preserves user edits.
        """
        marker = "<!-- Please enter your response above this line. -->"

        if self._active_editor_path:
            # Persistent file reuse: preserve previous edits, update prompt
            temp_path = self._active_editor_path
            try:
                with open(temp_path, "r", encoding="utf-8") as f:
                    existing = f.read()
                if marker in existing:
                    user_edits = existing.split(marker)[0].strip()
                    if user_edits:
                        content = f"{user_edits}\n\n{marker}\n\n{prompt}\n"
                    else:
                        content = f"\n\n{marker}\n\n{prompt}\n"
                else:
                    content = f"\n\n{marker}\n\n{prompt}\n"
            except Exception:
                content = f"\n\n{marker}\n\n{prompt}\n"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            temp_path = self._system_env.create_temp_file(suffix=".md")
            initial_content = f"\n\n{marker}\n\n{prompt}\n"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(initial_content)
            self._active_editor_path = temp_path

        editor_cmd = self._tooling.find_editor()
        if not editor_cmd:
            logger.info(
                "No editor configured. Please configure one in .teddy/config.yaml"
            )
            return ""
        editor_name = (
            os.path.basename(editor_cmd[0])
            if isinstance(editor_cmd, list) and editor_cmd
            else "editor"
        )
        logger.info("Opening Editor: %s", editor_name)

        # Classify editor: synchronous for CLI editors, async for GUI
        if self._is_cli_editor(editor_cmd):
            import subprocess  # noqa: PLC0415

            subprocess.run(editor_cmd + [temp_path])  # nosec B603
            self._flush_stdin()

            # Read harvested content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = self._strip_escape_sequences(content)
            marker = "<!-- Please enter your response above this line. -->"
            if marker in content:
                content = content.split(marker)[0].strip()

            # Clean up temp file (if it was newly created, not persistent)
            if temp_path == self._active_editor_path:
                self._system_env.delete_file(temp_path)
                self._active_editor_path = None

            return content if content else ""

        # GUI editor: fire-and-forget with Popen, return empty string to continue the loop
        import subprocess  # noqa: PLC0415

        subprocess.Popen(editor_cmd + [temp_path])  # nosec B603
        self._flush_stdin()
        return ""

    def _handle_empty_input(self, prompt: str) -> Optional[str]:
        """Handles logic when Enter is pressed without terminal input.

        If an editor has been opened (via _active_editor_path), harvest the content
        from the persistent file. Otherwise, prompt for confirmation.
        """
        if self._active_editor_path:
            # Flush main stdin buffer before reading file
            self._flush_stdin()
            try:
                with open(self._active_editor_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = self._strip_escape_sequences(content)
                marker = "<!-- Please enter your response above this line. -->"
                if marker in content:
                    content = content.split(marker)[0].strip()
                self._system_env.delete_file(self._active_editor_path)
                self._active_editor_path = None
                self._flush_stdin()
                return content if content else None
            except Exception:
                self._active_editor_path = None
                return None

        confirm = self._pt_prompt(
            "Press [Enter] again to confirm empty response › "
        ).strip()
        if not confirm:
            return ""
        if confirm.lower() == "e":
            content = self._launch_editor_background(prompt)
            if content:
                return content
            return None
        return confirm
