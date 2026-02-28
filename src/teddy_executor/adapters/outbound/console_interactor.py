import difflib
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import typer

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class ConsoleInteractorAdapter(IUserInteractor):
    def ask_question(self, prompt: str) -> str:
        """
        Presents a prompt to the user on the console and captures their input.
        Input is terminated by a single empty line on stdin.
        """
        typer.echo(prompt, err=True)

        lines = []
        while True:
            try:
                # Use typer.prompt to ensure it works correctly with CliRunner
                # We expect multiline input, so we don't use typer.prompt directly
                # for the whole block but line by line.
                line = input()
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)

    def _get_diff_content(self, action: ActionData) -> tuple[str, str, Path]:
        # --- Data Normalization for Diffing ---
        # This adapter normalizes the canonical ActionData from the parser to a flat
        # structure suitable for generating a diff.

        # 1. Normalize path from Markdown link
        # The parser normalizes "File Path" to "path"
        path_link = action.params.get("path", "")
        if isinstance(path_link, str) and path_link.endswith(")"):
            path_str = path_link.split("(")[-1].strip(")/")
        else:
            path_str = path_link

        if not path_str:
            # If there's no path, there's nothing to diff.
            return "", "", Path()

        path = Path(path_str)

        # 2. Get before/after content based on action type
        if action.type.lower() == "edit":
            before_content = path.read_text() if path.exists() else ""
            # The diff preview only supports the first edit block.
            edits = action.params.get("edits", [])
            if edits:
                first_edit = edits[0]
                find_block = first_edit.get("find", "")
                replace_block = first_edit.get("replace", "")
                after_content = before_content.replace(find_block, replace_block)
            else:
                # If no edits are provided, the content is unchanged.
                after_content = before_content
        else:  # create
            before_content = ""
            after_content = action.params.get("content", "")

        return before_content, after_content, path

    def _show_external_diff(
        self, tool_cmd: list[str], before_path: str, after_path: str
    ):
        """Launches an external diff tool as a non-blocking subprocess."""
        subprocess.run(tool_cmd + [before_path, after_path], check=True)

    def _show_in_terminal_diff(self, action: ActionData):
        before_content, after_content, path = self._get_diff_content(action)

        diff_generator = difflib.unified_diff(
            before_content.splitlines(keepends=True),
            after_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )

        # Iteratively build the diff string, ensuring each line is newline-terminated.
        # This fixes the bug where difflib doesn't add a newline to the last line
        # if the input content doesn't have one.
        diff_lines = []
        for line in diff_generator:
            diff_lines.append(line)
            if not line.endswith("\n"):
                diff_lines.append("\n")

        typer.echo("--- Diff ---", err=True)
        typer.echo("".join(diff_lines).rstrip(), err=True)
        typer.echo("------------", err=True)

    def _get_diff_viewer_command(self) -> list[str] | None:
        """Determines the command for an external diff viewer, if available."""
        custom_tool_str = os.getenv("TEDDY_DIFF_TOOL")
        if custom_tool_str:
            custom_tool_parts = shlex.split(custom_tool_str)
            tool_name = custom_tool_parts[0]

            if tool_path := shutil.which(tool_name):
                # Replace the command name with its full path for robustness
                custom_tool_parts[0] = tool_path
                return custom_tool_parts

            # If the user specified a tool but it wasn't found, warn them
            # and fall back to the terminal diff by returning None.
            typer.echo(
                f"Warning: Custom diff tool '{tool_name}' not found. "
                "Falling back to in-terminal diff.",
                err=True,
            )
            return None

        if code_path := shutil.which("code"):
            return [code_path, "-r", "--diff"]

        return None

    def confirm_action(
        self, action: ActionData, action_prompt: str
    ) -> tuple[bool, str]:
        temp_files = []
        try:
            if action.type.lower() in ["edit", "create"]:
                if diff_command := self._get_diff_viewer_command():
                    before_content, after_content, _ = self._get_diff_content(action)

                    before_file = tempfile.NamedTemporaryFile(
                        mode="w", delete=False, suffix=".before"
                    )
                    after_file = tempfile.NamedTemporaryFile(
                        mode="w", delete=False, suffix=".after"
                    )
                    temp_files.extend([before_file.name, after_file.name])

                    before_file.write(before_content)
                    before_file.close()

                    after_file.write(after_content)
                    after_file.close()

                    self._show_external_diff(
                        diff_command, before_file.name, after_file.name
                    )
                else:
                    self._show_in_terminal_diff(action)

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
                os.unlink(file_path)

    def notify_skipped_action(self, action: ActionData, reason: str) -> None:
        """Prints a colorized warning that an action was skipped."""
        message = f"[SKIPPED] {action.type}: {reason}"
        typer.secho(message, fg=typer.colors.YELLOW, err=True)
