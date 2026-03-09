from typing import Optional, Protocol
from teddy_executor.core.domain.models import ExecutionReport


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

    def transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        is_validation_failure: bool = False,
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
