from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import sys
from typing import TYPE_CHECKING, Optional

import typer
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import prompt as ptk_prompt

if TYPE_CHECKING:
    from teddy_executor.adapters.outbound.console_tooling import (
        ConsoleToolingHelper,
    )
    from teddy_executor.core.ports.outbound.system_environment import (
        ISystemEnvironment,
    )

# Regex to match ANSI SGR codes and OSC sequences
# - ANSI SGR: ESC [ <params> m  (e.g., \x1b[31m)
# - OSC sequences: ESC ] <params> ST (where ST is ESC \ or BEL \x07)
_ESCAPE_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x1b]*(?:\x1b\\|\x07)")

logger = logging.getLogger(__name__)


class ConsoleAskLoop:
    """Handles the interactive loop for capturing user response via terminal or editor."""

    def __init__(self, system_env: ISystemEnvironment, tooling: ConsoleToolingHelper):
        self._system_env = system_env
        self._tooling = tooling
        self._history = InMemoryHistory()
        self._active_editor_path: Optional[str] = None

    def _is_tty(self) -> bool:
        """Check if stdin is a real TTY (vs pipe/test runner)."""
        return sys.stdin.isatty()

    def _flush_stdin(self) -> None:
        """Flush stale escape sequences from the TTY input buffer.

        After an editor process exits, the terminal emulator may have written
        escape sequences into the shared stdin buffer. Flushing before the next
        prompt prevents them from being captured as user input.
        """
        if not self._is_tty():
            return
        try:
            import termios  # noqa: PLC0415

            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:  # nosec B110
            pass

    def _strip_escape_sequences(self, text: str) -> str:
        """Remove ANSI escape sequences and OSC control sequences from text."""
        return _ESCAPE_SEQUENCE_RE.sub("", text)

    def cleanup(self) -> None:
        """No-op cleanup method retained for backward compatibility."""

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
                prompt_text = "Editor opened. Terminal reply or [Enter] to confirm editor › "
            else:
                prompt_text = "Response (type 'e' for editor) › "
            raw_input = self._pt_prompt(prompt_text).strip()
            user_input = self._strip_escape_sequences(raw_input)

            if user_input.lower() == "e":
                content = self._launch_editor_background(prompt)
                if content:
                    return content
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

        editor_cmd = self._tooling.find_editor() or ["vim"]
        editor_name = editor_cmd[0] if isinstance(editor_cmd, list) else "editor"
        logger.info("Opening Editor: %s", editor_name)

        subprocess.Popen(  # nosec B603
            editor_cmd + [temp_path],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        # Non-blocking: return empty string to continue the loop
        return ""

    def _handle_empty_input(self, prompt: str) -> Optional[str]:
        """Handles logic when Enter is pressed without terminal input.

        If an editor has been opened (via _active_editor_path), harvest the content
        from the persistent file. Otherwise, prompt for confirmation.
        """
        if self._active_editor_path:
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

