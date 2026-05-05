from typing import Protocol, Optional, runtime_checkable, TYPE_CHECKING
from teddy_executor.core.domain.models.plan import Plan

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.project_context import ProjectContext


@runtime_checkable
class IPlanReviewer(Protocol):
    """
    Inbound port for the interactive review and modification of a Plan.
    """

    def review(
        self, plan: Plan, project_context: Optional["ProjectContext"] = None
    ) -> Optional[Plan]:
        """
        Initiates the interactive review process.
        """
        _ = project_context

        Returns:
            The modified Plan object, or None if the user cancels.
        """
        ...

    def review_action(
        self,
        action: "ActionData",
        total_actions: int,
        agent_name: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Initiates a sequential interactive review for a single action.

        Returns:
            A tuple of (should_execute, captured_message).
        """
        ...
