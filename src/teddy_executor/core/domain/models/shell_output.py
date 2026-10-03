from typing import TypedDict, NotRequired


class ShellOutput(TypedDict):
    """
    A strictly-typed dictionary representing the result of a shell command execution.
    """

    stdout: str
    stderr: str
    return_code: int
    failed_command: NotRequired[str]
    # Set by the shell adapter when a user interrupt terminated the in-flight
    # command (the process group was killed); the dispatcher maps this to
    # ActionStatus.INTERRUPTED.
    interrupted: NotRequired[bool]
