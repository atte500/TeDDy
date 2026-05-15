from typing import Protocol


class ISessionLoopGuard(Protocol):
    """
    Port for controlling the execution loop of a session.
    Allows for safety breaks in automated environments.
    """

    def should_continue(self, turn_count: int) -> bool:
        """
        Returns True if the loop should continue to the next turn.
        """
        ...
