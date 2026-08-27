from __future__ import annotations
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
        self._active_editor_path: Optional[str] = None
        self._active_editor_marker: Optional[str] = None
        self._history = InMemoryHistory()

    def _is_tty(self) -> bool:
        """Check if stdin is a real TTY (vs pipe/test runner)."""
        return sys.stdin.isatty()

    def _flush_stdin(self) -> None:
        """Flush stale escape sequences from the TTY input buffer.

        When a background editor process (with TTY attached) exits, the terminal
        emulator may have written escape sequences (e.g., OSC color responses)
        into the shared stdin buffer. Flushing these before the next prompt
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

    def _pt_prompt(self, prompt_text: str) -> str:
        """Prompt the user using prompt_toolkit (TTY) or input() (non-TTY/pipe)."""
        if not self._is_tty():
            # Non-TTY: fall back to input() for test compatibility (CliRunner, pipes, etc.)
            try:
                return input(prompt_text)
            except EOFError:
                return ""

        try:
            return ptk_prompt(prompt_text, history=self._history)
        except (EOFError, KeyboardInterrupt):
            return ""

    def run(self, prompt: str) -> str:
        """Orchestrates the interactive loop for capturing user response."""
        while True:
            prompt_label = "Response (type 'e' for editor) › "
            if self._active_editor_path:
                prompt_label = (
                    "Editor opened. Terminal reply or [Enter] to confirm editor › "
                )

            user_input = self._pt_prompt(prompt_label).strip()

            # Strip escape sequences unconditionally. Terminal emulator OSC
            # responses can arrive on stdin at any time (not just during editor
            # runtime), so we apply stripping to ALL input to prevent leaks
            # like ']10;rgb:8080/8989/b3b3' from becoming session names.
            user_input = self._strip_escape_sequences(user_input)

            if user_input.lower() == "e":
                self._launch_editor_background(prompt)
                self._flush_stdin()
                continue

            if self._active_editor_path:
                # Editor is active: ignore stdin entirely, always read the
                # editor temp file. The file is the source of truth and cannot
                # contain terminal escape sequences. Return whatever the user
                # wrote in the editor.
                return self._read_editor_result()

            if user_input:
                self.cleanup()
                return user_input

            response = self._handle_empty_input(prompt)
            if response is not None:
                return response

    def _handle_empty_input(self, prompt: str) -> Optional[str]:
        """Handles logic when Enter is pressed without terminal input."""
        if self._active_editor_path:
            return self._read_editor_result()

        confirm = self._pt_prompt(
            "Press [Enter] again to confirm empty response › "
        ).strip()

        if not confirm:
            return ""

        if confirm.lower() == "e":
            self._launch_editor_background(prompt)
            self._flush_stdin()
            return None

        return confirm

    def cleanup(self):
        """Removes the temp file and resets active state."""
        if self._active_editor_path:
            self._system_env.delete_file(self._active_editor_path)
            self._active_editor_path = None
            self._active_editor_marker = None

    def _launch_editor_background(self, prompt: str) -> None:
        """Opens a temporary file in a non-blocking external editor."""
        marker = "<!-- Please enter your response above this line. -->"
        initial_content = f"\n\n{marker}\n\n{prompt}\n"

        temp_path = self._system_env.create_temp_file(suffix=".md")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        editor_cmd = self._tooling.find_editor()
        if not editor_cmd:
            typer.echo("Error: No suitable editor found.", err=True)
            self._system_env.delete_file(temp_path)
            return

        try:
            cmd = editor_cmd + [temp_path]
            self._system_env.run_command(cmd, background=True)
            self._active_editor_path = temp_path
            self._active_editor_marker = marker
        except Exception as e:
            typer.echo(f"Error: Editor launch failed: {e}", err=True)
            self._system_env.delete_file(temp_path)

    def _read_editor_result(self) -> str:
        """Reads the content of the background editor's temp file."""
        if not self._active_editor_path:
            return ""

        try:
            with open(self._active_editor_path, "r", encoding="utf-8") as f:
                content = f.read()

            marker = self._active_editor_marker or ""
            if marker in content:
                content = content.split(marker)[0]

            return content.strip()
        except Exception as e:
            typer.echo(f"Error: Reading editor result failed: {e}", err=True)
            return ""
        finally:
            self.cleanup()
