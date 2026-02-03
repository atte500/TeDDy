import difflib
import os
import shlex
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

        print("--- Diff ---", file=sys.stderr)
        sys.stderr.write("".join(diff_lines).rstrip() + "\n")
        print("------------", file=sys.stderr)

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
            print(
                f"Warning: Custom diff tool '{tool_name}' not found. "
                "Falling back to in-terminal diff.",
                file=sys.stderr,
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
            if action.type in ["edit", "create_file"]:
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
        finally:
            for file_path in temp_files:
                os.unlink(file_path)
