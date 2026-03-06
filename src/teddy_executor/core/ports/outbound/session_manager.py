from typing import Protocol


class ISessionManager(Protocol):
    """
    Outbound port for managing turn directories and metadata persistence.
    """

    def create_session(self, name: str, agent_name: str) -> str:
        """
        Initializes a new session directory and bootstraps it for Turn 1.
        Returns the path to the new session directory.
        """
        ...

    def get_latest_turn(self, _session_name: str) -> str:
        """
        Identifies and returns the latest turn directory in the specified session.
        """
        ...
