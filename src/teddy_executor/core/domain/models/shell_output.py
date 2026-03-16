from typing import TypedDict, NotRequired


class ShellOutput(TypedDict):
    """
    A strictly-typed dictionary representing the result of a shell command execution.
    """

    stdout: str
    stderr: str
    return_code: int
    failed_command: NotRequired[str]
