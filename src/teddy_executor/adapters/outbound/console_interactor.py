import difflib
import shlex
from typing import Optional

import typer

from teddy_executor.core.domain.models.change_set import ChangeSet
from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class ConsoleInteractorAdapter(IUserInteractor):
    def __init__(self, system_env: ISystemEnvironment):
        self._system_env = system_env

    def ask_question(self, prompt: str) -> str:
        """
        Presents a prompt to the user on the console and captures their input.
        Allows falling back to an external editor for multi-line text.
        """
        typer.echo(prompt, err=True)
        typer.echo(
            "Press [Enter] to submit single-line response, or type 'e' + [Enter] to open in Editor:",
            err=True,
        )

        try:
            first_input = input().strip()
        except EOFError:
            return ""

        if first_input.lower() == "e":
            return self._get_input_from_editor(prompt)

        # If they typed a response immediately, return it.
        if first_input:
            return first_input

        # If they just pressed Enter, ask for confirmation.
        typer.echo(
            "Are you sure you want to submit an empty response? "
            "Press [Enter] again to confirm, type a response, or type 'e' to open in Editor:",
            err=True,
        )
        try:
            second_input = input().strip()
        except EOFError:
            return ""

        if second_input.lower() == "e":
            return self._get_input_from_editor(prompt)

        return second_input

    def _get_input_from_editor(self, prompt: str) -> str:
        """Opens a temporary file in an external editor and reads the response."""
        marker = "--- Please enter your response above this line. Save and close this file to submit. ---"
        initial_content = f"\n\n{marker}\n\n{prompt}\n"

        temp_path = self._system_env.create_temp_file(suffix=".md")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        editor = self._system_env.get_env("VISUAL") or self._system_env.get_env(
            "EDITOR"
        )
        if not editor:
            for fallback in ["code -w", "nano", "vim"]:
                cmd = fallback.split()[0]
                if self._system_env.which(cmd):
                    editor = fallback
                    break

        if not editor:
            typer.echo(
                "Error: No suitable editor found. Falling back to standard input.",
                err=True,
            )
            self._system_env.delete_file(temp_path)
            return self.ask_question("Please provide your response:")

        try:
            self._system_env.run_command(shlex.split(editor) + [temp_path])
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            if marker in content:
                content = content.split(marker)[0]

            return content.strip()

        except Exception as e:
            typer.echo(f"Error: Editor process failed: {e}", err=True)
            return ""
        finally:
            self._system_env.delete_file(temp_path)

    def _show_external_diff(
        self, tool_cmd: list[str], before_path: str, after_path: str
    ):
        """Launches an external diff tool."""
        self._system_env.run_command(tool_cmd + [before_path, after_path])

    def _show_new_file_preview(self, change_set: ChangeSet):
        """Displays a preview of a new file being created."""
        typer.echo("--- New File Preview ---", err=True)
        typer.echo(f"Path: {change_set.path}", err=True)
        typer.echo("Content:", err=True)
        typer.echo(change_set.after_content, err=True)
        typer.echo("------------------------", err=True)

    def _show_in_terminal_diff(self, change_set: ChangeSet):
        if change_set.action_type == "CREATE":
            self._show_new_file_preview(change_set)
            return

        diff_generator = difflib.unified_diff(
            change_set.before_content.splitlines(keepends=True),
            change_set.after_content.splitlines(keepends=True),
            fromfile=f"a/{change_set.path.name}",
            tofile=f"b/{change_set.path.name}",
        )

        diff_lines = []
        for line in diff_generator:
            diff_lines.append(line)
            if not line.endswith("\n"):
                diff_lines.append("\n")

        typer.echo("--- Diff ---", err=True)
        typer.echo("".join(diff_lines).rstrip(), err=True)
        typer.echo("------------", err=True)

    def _get_diff_viewer_command(self) -> Optional[list[str]]:
        """Determines the command for an external diff viewer, if available."""
        custom_tool_str = self._system_env.get_env("TEDDY_DIFF_TOOL")
        if custom_tool_str:
            custom_tool_parts = shlex.split(custom_tool_str)
            tool_name = custom_tool_parts[0]

            if tool_path := self._system_env.which(tool_name):
                custom_tool_parts[0] = tool_path
                return custom_tool_parts

            typer.echo(
                f"Warning: Custom diff tool '{tool_name}' not found. "
                "Falling back to in-terminal diff.",
                err=True,
            )
            return None

        if code_path := self._system_env.which("code"):
            return [code_path, "-r", "--diff"]

        return None

    def confirm_action(
        self,
        action: ActionData,
        action_prompt: str,
        change_set: Optional[ChangeSet] = None,
    ) -> tuple[bool, str]:
        temp_files = []
        try:
            if change_set:
                diff_command = self._get_diff_viewer_command()
                if not diff_command:
                    self._show_in_terminal_diff(change_set)
                elif change_set.action_type == "CREATE":
                    # Show a single-file preview in the editor
                    ext = "".join(change_set.path.suffixes)
                    preview_path = self._system_env.create_temp_file(
                        suffix=f".preview{ext}"
                    )
                    temp_files.append(preview_path)
                    with open(preview_path, "w", encoding="utf-8") as f:
                        f.write(change_set.after_content)

                    # Strip diff flags to open as a regular file
                    editor_cmd = [
                        arg
                        for arg in diff_command
                        if arg.lower() not in ("--diff", "-d")
                    ]
                    self._system_env.run_command(editor_cmd + [preview_path])
                else:
                    # Show a split-pane diff in the editor
                    ext = "".join(change_set.path.suffixes)
                    before_path = self._system_env.create_temp_file(
                        suffix=f".before{ext}"
                    )
                    after_path = self._system_env.create_temp_file(
                        suffix=f".after{ext}"
                    )
                    temp_files.extend([before_path, after_path])

                    with open(before_path, "w", encoding="utf-8") as f:
                        f.write(change_set.before_content)
                    with open(after_path, "w", encoding="utf-8") as f:
                        f.write(change_set.after_content)

                    self._show_external_diff(diff_command, before_path, after_path)

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
        message = f"[SKIPPED] {action.type}: {reason}"
        typer.secho(message, fg=typer.colors.YELLOW, err=True)

    def confirm_manual_handoff(
        self,
        action_type: str,
        target_agent: str | None,
        resources: list[str],
        message: str,
    ) -> tuple[bool, str]:
        """Displays a handoff request and asks for confirmation."""
        if action_type == "INVOKE":
            typer.secho(
                "--- HANDOFF REQUEST: INVOKE ---", fg=typer.colors.CYAN, err=True
            )
            typer.echo(
                "The current agent is requesting a handoff to the agent below.\n",
                err=True,
            )
            if target_agent:
                typer.echo(f"▶ Target Agent: {target_agent}", err=True)
            typer.echo(f"▶ Handoff Message:\n{message}\n", err=True)
        else:  # RETURN
            typer.secho(
                "--- HANDOFF NOTIFICATION: RETURN ---", fg=typer.colors.CYAN, err=True
            )
            typer.echo(
                "The current agent has completed its task and is returning control.\n",
                err=True,
            )
            typer.echo(f"▶ Return Message:\n{message}\n", err=True)

        if resources:
            typer.echo("▶ Handoff Resources:", err=True)
            typer.echo("\n".join(resources), err=True)

        typer.echo("", err=True)  # Spacer
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
