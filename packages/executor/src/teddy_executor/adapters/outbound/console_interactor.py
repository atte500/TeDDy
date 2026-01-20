import difflib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class ConsoleInteractorAdapter(IUserInteractor):
    def ask_question(self, prompt: str) -> str:
        """
        Presents a prompt to the user on the console and captures their input.
        Input is terminated by a single empty line on stdin.
        """
        # Print prompt to stderr so it doesn't interfere with stdout scraping in tests
        print(prompt, file=sys.stderr, flush=True)

        lines = []
        while True:
            try:
                line = input()
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)

    def _get_diff_content(self, action: ActionData) -> tuple[str, str, Path]:
        path_str = action.params["path"]
        path = Path(path_str)
        if action.type == "edit":
            before_content = path.read_text()
            after_content = before_content.replace(
                action.params["find"], action.params["replace"]
            )
        else:  # create_file
            before_content = ""
            after_content = action.params["content"]
        return before_content, after_content, path

    def _show_external_diff(self, tool_cmd: list[str], action: ActionData):
        before_content, after_content, _ = self._get_diff_content(action)

        with (
            tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".before"
            ) as before_file,
            tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".after"
            ) as after_file,
        ):
            before_file.write(before_content)
            after_file.write(after_content)
            before_path = before_file.name
            after_path = after_file.name

        try:
            subprocess.run(tool_cmd + [before_path, after_path], check=True)
        finally:
            os.unlink(before_path)
            os.unlink(after_path)

    def _show_in_terminal_diff(self, action: ActionData):
        before_content, after_content, path = self._get_diff_content(action)

        diff = difflib.unified_diff(
            before_content.splitlines(keepends=True),
            after_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
        print("--- Diff ---", file=sys.stderr)
        for line in diff:
            print(line, end="", file=sys.stderr)
        print("------------", file=sys.stderr)

    def _get_diff_viewer_command(self) -> list[str] | None:
        """Determines the command for an external diff viewer, if available."""
        custom_tool_name = os.getenv("TEDDY_DIFF_TOOL")
        if custom_tool_name:
            if custom_tool_path := shutil.which(custom_tool_name):
                return [custom_tool_path]

        if code_path := shutil.which("code"):
            return [code_path, "--wait", "--diff"]

        return None

    def confirm_action(
        self, action: ActionData, action_prompt: str
    ) -> tuple[bool, str]:
        if action.type in ["edit", "create_file"]:
            if diff_command := self._get_diff_viewer_command():
                self._show_external_diff(diff_command, action)
            else:
                self._show_in_terminal_diff(action)

        try:
            prompt = f"{action_prompt}\nApprove? (y/n): "
            # Use stderr for prompts to not pollute stdout
            print(prompt, file=sys.stderr, flush=True, end="")
            response = input().lower().strip()

            if response.startswith("y"):
                return True, ""

            reason_prompt = "Reason for skipping (optional): "
            print(reason_prompt, file=sys.stderr, flush=True, end="")
            reason = input().strip()
            return False, reason
        except EOFError:
            # If input stream is closed (e.g., in non-interactive script),
            # default to denying the action.
            print("\n", file=sys.stderr, flush=True)  # Ensure a newline after prompt
            return False, "Skipped due to non-interactive session."
