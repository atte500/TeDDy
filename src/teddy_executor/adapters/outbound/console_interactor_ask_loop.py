from __future__ import annotations
import os
import re
import sys
from typing import TYPE_CHECKING, Optional

import typer
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import prompt as ptk_prompt

if TYPE_CHECKING:
    from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper


# Regex to match ANSI SGR codes and OSC sequences
# - ANSI SGR: ESC [ <params> m  (e.g., \x1b[31m)
# - OSC sequences: ESC ] <params> ST (where ST is ESC \ or BEL \x07)
_ESCAPE_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x1b]*(?:\x1b\\|\x07)")


class ConsoleAskLoop:
    """Handles the interactive loop for capturing user response via terminal or editor."""

    def __init__(self, system_env: ISystemEnvironment, tooling: ConsoleToolingHelper):
        self._system_env = system_env
        self._tooling = tooling
        self._history = InMemoryHistory()

    def _is_tty(self) -> bool:
        """Check if stdin is a real TTY (vs pipe/test runner)."""
        return sys.stdin.isatty()

    def _flush_stdin(self) -> None:
        """Flush stale escape sequences from the TTY input buffer.

        After an editor process (with TTY attached) exits, the terminal
        emulator may have written escape sequences (e.g., OSC color responses)
        into the shared stdin buffer. Flushing before the next prompt
        prevents them from being captured as user input.
        """
        if not self._is_tty():
            return
        try:
            import termios  # noqa: PLC0415
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:  # nosec B110
            # Not all platforms support termios; safe to ignore.
            pass

    def _strip_escape_sequences(self, text: str) -> str:
        """Remove ANSI escape sequences and OSC control sequences from text.

        This prevents terminal emulator escape sequences (e.g., color sync
        responses written during editor runtime) from leaking into user input.

        Returns the cleaned text with escape sequences removed.
        """
        return _ESCAPE_SEQUENCE_RE.sub("", text)

    def cleanup(self) -> None:
        """No-op cleanup method retained for backward compatibility.

        Previously used to clean up background editor state. The synchronous
        editor flow no longer requires cleanup, but the method is kept to
        avoid breaking callers.
        """

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
        opens an external editor **synchronously** (blocking Python entirely),
        giving the editor exclusive access to the TTY. After the editor exits,
        the file content is read and returned if non-empty.
        """
        while True:
            user_input = self._pt_prompt("Response (type 'e' for editor) › ").strip()

            # Strip escape sequences unconditionally.
            user_input = self._strip_escape_sequences(user_input)

            if user_input.lower() == "e":
                # Open editor synchronously: Python blocks, editor has exclusive TTY.
                content = self._open_editor_blocking(prompt)
                if content:
                    return content
                # Empty editor content: back to normal prompt
                continue

            if user_input:
                return user_input

            response = self._handle_empty_input(prompt)
            if response is not None:
                return response

    def _handle_empty_input(self, prompt: str) -> Optional[str]:
        """Handles logic when Enter is pressed without terminal input."""
        confirm = self._pt_prompt(
            "Press [Enter] again to confirm empty response › "
        ).strip()
        if not confirm:
            return ""
        if confirm.lower() == "e":
            content = self._open_editor_blocking(prompt)
            if content:
                return content
            return None
        return confirm

    def _open_editor_blocking(self, prompt: str) -> str:
        """Opens a temporary file in an external editor synchronously.

        Python blocks until the editor exits. The editor has exclusive access
        to the TTY, preventing race conditions between the editor and
        prompt_toolkit on the same terminal. After the editor exits, the TTY
        buffer is flushed to remove any leftover escape sequences.

        Returns the user's content from the file (stripped), or empty string
        if the file was empty or an error occurred.
        """
        marker = "<!-- Please enter your response above this line. -->"
        initial_content = f"\n\n{marker}\n\n{prompt}\n"

        temp_path = self._system_env.create_temp_file(suffix=".md")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(initial_content)

            editor_cmd = self._tooling.find_editor()
            if not editor_cmd:
                typer.echo("Error: No suitable editor found.", err=True)
                return ""

            cmd = editor_cmd + [temp_path]

            # Optional: suppress Vim's terminal color queries to reduce OSC
            # sequences from being written to the TTY during editor runtime.
            saved_viminit = os.environ.get("VIMINIT")
            try:
                os.environ["VIMINIT"] = "set t_u7= t_RF= t_RB="
                self._system_env.run_command(cmd)
            finally:
                if saved_viminit is None:
                    os.environ.pop("VIMINIT", None)
                else:
                    os.environ["VIMINIT"] = saved_viminit

            # Flush the TTY buffer after the editor has fully exited.
            self._flush_stdin()

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            if marker in content:
                content = content.split(marker)[0]

            return content.strip()
        except Exception as e:
            typer.echo(f"Error: Editor launch failed: {e}", err=True)
            return ""
        finally:
            self._system_env.delete_file(temp_path)
