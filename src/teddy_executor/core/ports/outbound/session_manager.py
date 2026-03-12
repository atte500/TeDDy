from enum import Enum
from typing import Optional, Protocol
from teddy_executor.core.domain.models import ExecutionReport


class SessionState(Enum):
    """Represents the current state of a session based on its latest turn."""

    EMPTY = "EMPTY"  # No plan.md exists
    PENDING_PLAN = "PENDING_PLAN"  # plan.md exists, but no report.md
    COMPLETE_TURN = "COMPLETE_TURN"  # report.md exists


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

    def get_session_state(self, session_name: str) -> tuple[SessionState, str]:
        """
        Determines the state of the session and returns the state and the path
        to the latest turn.
        """
        ...

    def transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        is_validation_failure: bool = False,
        turn_cost: float = 0.0,
    ) -> str:
        """
        Calculates and creates the next turn directory based on the current turn
        and the outcome of its plan.
        """
        ...

    def resolve_context_paths(self, plan_path: str) -> dict[str, list[str]]:
        """
        Locates context files relative to the plan path and returns their contents.
        """
        ...

    def rename_session(self, old_name: str, new_name: str) -> str:
        """
        Safely renames a session directory on the filesystem.
        Returns the new path to the session directory.
        """
        ...

    def get_latest_session_name(self) -> str:
        """
        Identifies and returns the name of the most recently modified session.
        """
        ...

    def resolve_session_from_path(self, path: str) -> str:
        """
        Resolves a session name from a given path (session root, turn dir, or file).
        """
        ...
