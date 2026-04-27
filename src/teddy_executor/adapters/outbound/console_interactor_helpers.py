import logging
import sys
from typing import List, Optional

import typer

from teddy_executor.adapters.inbound.cli_formatter import (
    echo_handoff_details,
    echo_skipped_action,
)
from teddy_executor.core.domain.models.change_set import ChangeSet

logger = logging.getLogger(__name__)


def restore_terminal_mode():
    """Restores stdin to canonical/echo mode (Unix only)."""
    import os

    if sys.platform == "win32" or "PYTEST_CURRENT_TEST" in os.environ:
        return

    try:
        import termios

        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        # iflags: Ensure ICRNL is set (Map CR to NL on input)
        attrs[0] = attrs[0] | termios.ICRNL
        # lflags: Re-enable canonical mode (ICANON) and echo (ECHO)
        attrs[3] = (
            attrs[3] | termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN
        )
        # Apply changes and FLUSH the input buffer
        termios.tcsetattr(fd, termios.TCSAFLUSH, attrs)
    except Exception as e:
        logger.debug("Failed to restore terminal mode: %s", e)


def prepare_external_preview_files(
    system_env, change_set: ChangeSet, temp_files: List[str]
) -> List[str]:
    """Sets up temp files for external diff/editor."""
    ext = "".join(change_set.path.suffixes)
    if change_set.action_type == "CREATE":
        preview_path = system_env.create_temp_file(suffix=f".preview{ext}")
        temp_files.append(preview_path)
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(change_set.after_content)
        return [preview_path]

    before_path = system_env.create_temp_file(suffix=f".before{ext}")
    after_path = system_env.create_temp_file(suffix=f".after{ext}")
    temp_files.extend([before_path, after_path])
    with open(before_path, "w", encoding="utf-8") as f:
        f.write(change_set.before_content)
    with open(after_path, "w", encoding="utf-8") as f:
        f.write(change_set.after_content)
    return [before_path, after_path]


def display_handoff_and_confirm(
    action_type: str,
    target_agent: Optional[str],
    resources: List[str],
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


def print_skipped_action(action, reason: str) -> None:
    """Prints a colorized warning that an action was skipped."""
    echo_skipped_action(action, reason)
