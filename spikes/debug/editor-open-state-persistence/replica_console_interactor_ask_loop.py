"""Sandbox replica of the ask loop with pending-draft cleanup.

The replica mirrors ``console_interactor_ask_loop.py`` and changes only the
exit paths that abandoned an opened but unharvested editor draft: the
terminal-reply return and the failed-harvest return.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import prompt as ptk_prompt

from teddy_executor.adapters.outbound.console_interactor_helpers import (
    restore_terminal_mode,
)
from teddy_executor.core.utils.editor_names import is_cli_editor
from teddy_executor.core.utils.stdin_ownership import stdin_owned

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
        """Flush stale escape sequences from the TTY input buffer."""
        if not self._is_tty():
            return
        try:
            import termios  # noqa: PLC0415

            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except ImportError:
            try:
                import msvcrt  # noqa: PLC0415

                while msvcrt.kbhit():
                    msvcrt.getwch()
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
        except EOFError:
            return ""

    def run(self, prompt: str) -> str:
        """Orchestrates the interactive loop for capturing user response."""
        with stdin_owned():
            while True:
                if self._active_editor_path:
                    prompt_text = (
                        "Editor opened. Terminal reply or [Enter] to confirm editor › "
                    )
                else:
                    prompt_text = "Response (type 'e' for editor) › "
                raw_input = self._pt_prompt(prompt_text).strip()
                if self._active_editor_path:
                    user_input = self._strip_escape_sequences(raw_input)
                else:
                    user_input = raw_input

                if user_input.lower() == "e":
                    content = self._launch_editor_background(prompt)
                    if content:
                        return content
                    self._flush_stdin()
                    continue

                if user_input:
                    self._discard_pending_draft()
                    return user_input

                response = self._handle_empty_input(prompt)
                if response is not None:
                    return response

    def _discard_pending_draft(self) -> None:
        """Deletes an abandoned editor draft and clears the pending state.

        A draft is abandoned when the user answers in the terminal instead of
        harvesting the opened editor. Keeping it pins the next turn to the
        "Editor opened" prompt and leaves the temp file on disk.
        """
        if not self._active_editor_path:
            return
        temp_path = self._active_editor_path
        self._active_editor_path = None
        self._system_env.delete_file(temp_path)

    def _launch_editor_background(self, prompt: str) -> str:
        """Opens an external editor and returns the harvested content when blocking."""
        marker = "<!-- Please enter your response above this line. -->"

        editor_cmd = self._tooling.find_editor()
        if not editor_cmd:
            logger.info(
                "Editor is disabled in config. Set 'editor' in .teddy/config.yaml to enable."
            )
            return ""

        if self._active_editor_path:
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
        editor_name = (
            os.path.basename(editor_cmd[0])
            if isinstance(editor_cmd, list) and editor_cmd
            else "editor"
        )
        logger.info("Opening Editor: %s", editor_name)

        if is_cli_editor(editor_cmd):
            import subprocess  # noqa: PLC0415

            subprocess.run(editor_cmd + [temp_path])  # nosec B603
            restore_terminal_mode()
            self._flush_stdin()

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = self._strip_escape_sequences(content)
            marker = "<!-- Please enter your response above this line. -->"
            if marker in content:
                content = content.split(marker)[0].strip()

            if temp_path == self._active_editor_path:
                self._system_env.delete_file(temp_path)
                self._active_editor_path = None

            return content if content else ""

        import subprocess  # noqa: PLC0415

        popen_kwargs: dict = {}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(editor_cmd + [temp_path], **popen_kwargs)  # nosec B603
        self._flush_stdin()
        return ""

    def _handle_empty_input(self, prompt: str) -> Optional[str]:
        """Harvests an opened editor draft, or confirms an empty response."""
        if self._active_editor_path:
            temp_path = self._active_editor_path
            self._active_editor_path = None
            self._flush_stdin()
            try:
                with open(temp_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as exc:
                logger.warning("Could not read the editor draft %s: %s", temp_path, exc)
                self._system_env.delete_file(temp_path)
                return None
            content = self._strip_escape_sequences(content)
            marker = "<!-- Please enter your response above this line. -->"
            if marker in content:
                content = content.split(marker)[0].strip()
            self._system_env.delete_file(temp_path)
            self._flush_stdin()
            return content if content else None

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