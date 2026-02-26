from typing import TypedDict


class ShellOutput(TypedDict):
    """
    A strictly-typed dictionary representing the result of a shell command execution.
    """

    stdout: str
    stderr: str
    return_code: int
