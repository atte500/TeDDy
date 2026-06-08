from __future__ import annotations
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper


class ConsoleAskLoop:
    """Handles the interactive loop for capturing user response via terminal or editor."""

    def __init__(self, system_env: ISystemEnvironment, tooling: ConsoleToolingHelper):
        self._system_env = system_env
        self._tooling = tooling
        self._active_editor_path: Optional[str] = None
        self._active_editor_marker: Optional[str] = None

    def run(self, prompt: str) -> str:
        """Orchestrates the interactive loop for capturing user response."""
        while True:
            prompt_label = "Response (type 'e' for editor) › "
            if self._active_editor_path:
                prompt_label = (
                    "Editor opened. Terminal reply or [Enter] to confirm editor › "
                )

            typer.echo(prompt_label, nl=False, err=True)
            try:
                user_input = input().strip()
            except EOFError:
                self.cleanup()
                return ""

            if user_input.lower() == "e":
                self._launch_editor_background(prompt)
                continue

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

        typer.echo(
            "Press [Enter] again to confirm empty response › ",
            nl=False,
            err=True,
        )
        try:
            confirm = input().strip()
        except EOFError:
            return ""

        if not confirm:
            return ""

        if confirm.lower() == "e":
            self._launch_editor_background(prompt)
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
