"""
Validation rules for the 'EXECUTE' action.
"""

import os
from typing import List, Optional

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.services.validation_rules.helpers import ValidationError


def _check_for_disallowed_chaining(command: str) -> Optional[ValidationError]:
    """Checks for '&&' outside of quotes."""
    in_single_quotes = False
    in_double_quotes = False
    for i, char in enumerate(command):
        if char == "'" and not in_double_quotes:
            in_single_quotes = not in_single_quotes
        elif char == '"' and not in_single_quotes:
            in_double_quotes = not in_double_quotes

        if not in_single_quotes and not in_double_quotes:
            if char == "&" and i + 1 < len(command) and command[i + 1] == "&":
                return ValidationError(
                    message="Command chaining with '&&' is not allowed"
                )
    return None


def _check_for_multiple_commands(command: str) -> Optional[ValidationError]:
    """
    Checks for multiple commands, respecting quotes and line continuations.

    A newline is considered a command separator only if it is not inside
    a quoted string and is not escaped by a backslash.
    """
    in_single_quotes = False
    in_double_quotes = False
    processed_chars = []

    # Parse the command string character by character to correctly handle
    # newlines inside quotes and line continuations.
    i = 0
    while i < len(command):
        char = command[i]

        # Handle line continuation: if `\` is followed by `\n`, skip both.
        if char == "\\" and i + 1 < len(command) and command[i + 1] == "\n":
            i += 2  # Skip both `\` and `\n`
            continue

        # Toggle state based on quotes. This simple state machine doesn't
        # handle escaped quotes, but is sufficient for this validation.
        if char == "'" and not in_double_quotes:
            in_single_quotes = not in_single_quotes
        elif char == '"' and not in_single_quotes:
            in_double_quotes = not in_double_quotes

        # If a newline is found inside an open quote, replace it with a
        # space to neutralize it. Otherwise, preserve it as a potential
        # command separator.
        if char == "\n" and (in_single_quotes or in_double_quotes):
            processed_chars.append(" ")
        else:
            processed_chars.append(char)

        i += 1

    processed_command = "".join(processed_chars)
    lines = processed_command.split("\n")

    command_lines = [
        line.strip()
        for line in lines
        if line.strip()
        and not line.strip().startswith("cd ")
        and not line.strip().startswith("export ")
    ]

    if len(command_lines) > 1:
        return ValidationError(
            message="EXECUTE action must contain exactly one command"
        )
    return None


def _check_cwd_safety(cwd: str) -> Optional[ValidationError]:
    """Checks if the cwd is safe (not absolute, no traversal)."""
    if os.path.isabs(cwd):
        return ValidationError(
            message=f"CWD '{cwd}' is an absolute path and is not allowed"
        )
    # Check for path traversal attempts
    if ".." in cwd.split(os.path.sep):
        return ValidationError(message=f"CWD '{cwd}' is outside the project directory")
    return None


def validate_execute_action(action: ActionData) -> List[ValidationError]:
    """Validates an 'execute' action."""
    errors: List[ValidationError] = []
    command = action.params.get("command", "")
    cwd = action.params.get("cwd")

    if cwd:
        if error := _check_cwd_safety(cwd):
            errors.append(error)

    if command:
        if error := _check_for_disallowed_chaining(command):
            errors.append(error)

        if error := _check_for_multiple_commands(command):
            errors.append(error)

    return errors
