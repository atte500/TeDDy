import shlex
from typing import List, Optional

import typer
from rich.console import Console

from teddy_executor.adapters.inbound.cli_formatter import (
    echo_diff_preview,
    echo_plan_summary,
)
from teddy_executor.core.domain.models.change_set import ChangeSet
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)
from teddy_executor.adapters.outbound.console_interactor_helpers import (
    display_handoff_and_confirm,
    prepare_external_preview_files,
    print_skipped_action,
    restore_terminal_mode,
)


class ConsoleInteractorAdapter(IUserInteractor):
    def __init__(self, system_env: ISystemEnvironment, config_service: IConfigService):
        self._system_env = system_env
        self._config_service = config_service
        self._tooling = ConsoleToolingHelper(system_env, config_service)
        self._console = Console(stderr=True)
        self._ask_loop = ConsoleAskLoop(self._system_env, self._tooling)

    def _restore_terminal(self):
        """Restores stdin to canonical/echo mode (Unix only)."""
        restore_terminal_mode()

    def prompt(self, text: str, default: str = "") -> str:
        """Prompts the user using typer.prompt."""
        return typer.prompt(text, default=default, show_default=False, err=True)

    def prompt_for_message(
        self, initial_message: Optional[str] = None
    ) -> Optional[str]:
        """Opens the external editor to capture a user message."""
        import os

        mock_output = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
        if mock_output:
            return mock_output

        return self._launch_editor_synchronous(initial_message or "")

    def display_message(self, message: str) -> None:
        """Displays a message using Rich console to ensure consistent coloring."""
        self._console.print(message)

    async def async_display_message(self, message: str) -> None:
        """Asynchronously displays an informational message."""
        import anyio

        await anyio.to_thread.run_sync(self.display_message, message)

    async def async_ask_question(
        self,
        prompt: str,
        resources: list[str] | None = None,
        agent_name: Optional[str] = None,
    ) -> str:
        """Asynchronously asks the user a question."""
        import anyio

        return await anyio.to_thread.run_sync(
            self.ask_question, prompt, resources, agent_name
        )

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
        self._ask_loop.cleanup()
        return self._ask_loop.run(prompt)

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

    def _launch_editor_synchronous(self, initial_content: str) -> str:
        """Opens a temporary file in an external editor and waits for it to close."""
        import os

        mock_output = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
        if mock_output:
            return mock_output

        temp_path = self._system_env.create_temp_file(suffix=".md")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(initial_content)

            editor_cmd = self._tooling.find_editor()
            if not editor_cmd:
                typer.echo("Error: No suitable editor found.", err=True)
                return ""

            cmd = editor_cmd + [temp_path]
            self._system_env.run_command(cmd)
            self._restore_terminal()

            with open(temp_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            typer.echo(f"Error: Editor launch failed: {e}", err=True)
            return ""
        finally:
            self._system_env.delete_file(temp_path)

    def confirm_plan_review(self, plan: Plan) -> bool:
        """Displays a summary of the plan and asks for bulk confirmation."""
        echo_plan_summary(plan)
        try:
            prompt = "\nExecute this plan? (y/n): "
            response = typer.prompt(prompt, default="n", show_default=False, err=True)
            return response.lower().strip().startswith("y")
        except (EOFError, typer.Abort):
            return False

    def _handle_external_preview(
        self, change_set: ChangeSet, diff_command: List[str], temp_files: List[str]
    ) -> None:
        """Sets up temp files and launches external diff/editor (Non-blocking)."""
        paths = prepare_external_preview_files(self._system_env, change_set, temp_files)

        if change_set.action_type == "CREATE":
            cmd = [c for c in diff_command if c.lower() not in ("--diff", "-d")]
            self._system_env.run_command(cmd + paths, background=True)
        else:
            self._system_env.run_command(diff_command + paths, background=True)

    def confirm_action(
        self,
        action: ActionData,
        action_prompt: str,
        change_set: Optional[ChangeSet] = None,
    ) -> tuple[bool, str]:
        # Always restore TTY before starting an interaction block
        self._restore_terminal()
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
                    self._restore_terminal()

            message = ""
            while True:
                prompt = f"{action_prompt}\nApprove? (y/n/m): "
                # Use typer.prompt which handles echoing to stderr correctly
                response = (
                    typer.prompt(prompt, default="n", show_default=False, err=True)
                    .lower()
                    .strip()
                )

                if response.startswith("y"):
                    return True, message

                if response.startswith("m"):
                    message = self._launch_editor_synchronous("")
                    continue

                return False, ""
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
        print_skipped_action(action, reason)

    def confirm_manual_handoff(
        self,
        action_type: str,
        target_agent: str | None,
        resources: list[str],
        message: str,
    ) -> tuple[bool, str]:
        """Displays a handoff request and asks for confirmation."""
        return display_handoff_and_confirm(
            action_type, target_agent, resources, message
        )
