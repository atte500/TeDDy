from typing import Optional, Protocol


class ISessionLoopGuard(Protocol):
    """
    Port for controlling the execution loop of a session.
    Allows for safety breaks in automated environments.
    """

    def should_continue(
        self, turn_count: int, cumulative_cost: float, interactive: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Returns (True, None) if the loop should continue to the next turn.
        Returns (False, reason) when a guardrail limit is hit, where `reason`
        is a human-readable message explaining which limit was exceeded and
        how to adjust the configuration.
        """
        ...
