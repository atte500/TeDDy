import shlex
from typing import List, Optional

import typer
from rich.console import Console

from teddy_executor.adapters.inbound.cli_helpers import (
    echo_diff_preview,
    echo_handoff_details,
    echo_skipped_action,
)
from teddy_executor.core.domain.models.change_set import ChangeSet
from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper


class ConsoleInteractorAdapter(IUserInteractor):
    def __init__(self, system_env: ISystemEnvironment):
        self._system_env = system_env
        self._tooling = ConsoleToolingHelper(system_env)
        self._console = Console(stderr=True)
        self._active_editor_path: Optional[str] = None
        self._active_editor_marker: Optional[str] = None

    def prompt(self, text: str, default: str = "") -> str:
        """Prompts the user using typer.prompt."""
        return typer.prompt(text, default=default, show_default=False, err=True)

    def display_message(self, message: str) -> None:
        """Displays a message using Typer echo to ensure visibility and testability."""
        typer.echo(message, err=True)

    def ask_question(
        self,
        prompt: str,
        resources: list[str] | None = None,
        agent_name: Optional[str] = None,
    ) -> str:
        """
        Presents a prompt to the user on the console and captures their input.
        Allows falling back to an external editor for multi-line text.
        """
        self._display_ask_header(prompt, resources, agent_name)

        self._active_editor_path = None
        self._active_editor_marker = None

        return self._run_prompt_loop(prompt)

    def _display_ask_header(
        self, prompt: str, resources: list[str] | None, agent_name: Optional[str]
    ) -> None:
        """Displays the formatted message header and reference files."""
        display_name = agent_name if agent_name else "TeDDy"
        header = f"--- MESSAGE from {display_name} ---"
        typer.secho(header, fg=typer.colors.CYAN, err=True)
        typer.echo(prompt, err=True)

        if resources:
            typer.echo("\n▶ Reference Files:", err=True)
            typer.echo("\n".join(resources), err=True)
        typer.echo("", err=True)  # Spacer

    def _run_prompt_loop(self, prompt: str) -> str:
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
                self._cleanup_editor()
                return ""

            # 1. Trigger Editor
            if user_input.lower() == "e":
                self._launch_editor_background(prompt)
                continue

            # 2. Terminal Reply (Non-empty)
            if user_input:
                self._cleanup_editor()
                return user_input

            # 3. Empty Input
            response = self._handle_empty_input(prompt)
            if response is not None:
                return response

    def _handle_empty_input(self, prompt: str) -> Optional[str]:
        """Handles logic when Enter is pressed without terminal input."""
        # If editor was open, [Enter] confirms and reads it.
        if self._active_editor_path:
            return self._read_editor_result()

        # Otherwise, confirm empty response to prevent accidental submission
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

        # Recursive-like behavior for 'e' in confirm prompt
        if confirm.lower() == "e":
            self._launch_editor_background(prompt)
            return None

        return confirm

    def _cleanup_editor(self):
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

        editor = self._tooling.find_editor()
        if not editor:
            typer.echo("Error: No suitable editor found.", err=True)
            self._system_env.delete_file(temp_path)
            return

        try:
            cmd = shlex.split(editor) + [temp_path]
            self._system_env.run_command(cmd, background=True)
            self._active_editor_path = temp_path
            self._active_editor_marker = marker
            typer.echo("Editor opened in background.", err=True)
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
            self._cleanup_editor()

    def _handle_external_preview(
        self, change_set: ChangeSet, diff_command: List[str], temp_files: List[str]
    ) -> None:
        """Sets up temp files and launches external diff/editor."""
        ext = "".join(change_set.path.suffixes)
        if change_set.action_type == "CREATE":
            preview_path = self._system_env.create_temp_file(suffix=f".preview{ext}")
            temp_files.append(preview_path)
            with open(preview_path, "w", encoding="utf-8") as f:
                f.write(change_set.after_content)
            # Strip diff flags to open as a regular file
            cmd = [c for c in diff_command if c.lower() not in ("--diff", "-d")]
            self._system_env.run_command(cmd + [preview_path])
        else:
            before_path = self._system_env.create_temp_file(suffix=f".before{ext}")
            after_path = self._system_env.create_temp_file(suffix=f".after{ext}")
            temp_files.extend([before_path, after_path])
            with open(before_path, "w", encoding="utf-8") as f:
                f.write(change_set.before_content)
            with open(after_path, "w", encoding="utf-8") as f:
                f.write(change_set.after_content)
            self._system_env.run_command(diff_command + [before_path, after_path])

    def confirm_action(
        self,
        action: ActionData,
        action_prompt: str,
        change_set: Optional[ChangeSet] = None,
    ) -> tuple[bool, str]:
        temp_files: List[str] = []
        try:
            if change_set:
                diff_command = self._tooling.get_diff_viewer_command()
                if not diff_command:
                    # Check if failure was due to a missing custom tool
                    custom_tool = self._system_env.get_env("TEDDY_DIFF_TOOL")
                    if custom_tool:
                        tool_name = shlex.split(custom_tool)[0]
                        typer.echo(
                            f"Warning: Custom diff tool '{tool_name}' not found. "
                            "Falling back to in-terminal diff.",
                            err=True,
                        )
                    echo_diff_preview(change_set)
                else:
                    self._handle_external_preview(change_set, diff_command, temp_files)

            prompt = f"{action_prompt}\nApprove? (y/n): "
            # Use typer.prompt which handles echoing to stderr correctly
            response = typer.prompt(prompt, default="n", show_default=False, err=True)

            if response.lower().strip().startswith("y"):
                return True, ""

            reason_prompt = "Reason for skipping (optional): "
            reason = typer.prompt(
                reason_prompt, default="", show_default=False, err=True
            )
            return False, reason
        except (EOFError, typer.Abort):
            # If input stream is closed (e.g., in non-interactive script),
            # default to denying the action.
            typer.echo("\nAborted.", err=True)
            return False, "Skipped due to non-interactive session."
        finally:
            for file_path in temp_files:
                self._system_env.delete_file(file_path)

    def notify_skipped_action(self, action: ActionData, reason: str) -> None:
        """Prints a colorized warning that an action was skipped."""
        echo_skipped_action(action, reason)

    def confirm_manual_handoff(
        self,
        action_type: str,
        target_agent: str | None,
        resources: list[str],
        message: str,
    ) -> tuple[bool, str]:
        """Displays a handoff request and asks for confirmation."""
        echo_handoff_details(action_type, target_agent, resources, message)
        try:
            response = typer.prompt(
                "Press [Enter] to approve, or type a reason for rejection",
                default="",
                show_default=False,
                err=True,
            )

            if response:
                return False, response  # Rejected
            return True, ""  # Approved
        except (EOFError, typer.Abort):
            typer.echo("\nAborted.", err=True)
            return False, "Skipped due to non-interactive session."
