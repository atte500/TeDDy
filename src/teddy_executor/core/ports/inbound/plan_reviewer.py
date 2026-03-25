from typing import Protocol, Optional, runtime_checkable, TYPE_CHECKING
from teddy_executor.core.domain.models.plan import Plan

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData


@runtime_checkable
class IPlanReviewer(Protocol):
    """
    Inbound port for the interactive review and modification of a Plan.
    """

    def review(self, plan: Plan) -> Optional[Plan]:
        """
        Initiates the interactive review process.

        Returns:
            The modified Plan object, or None if the user cancels.
        """
        ...

    def review_action(
        self,
        action: "ActionData",
        total_actions: int,
        agent_name: Optional[str] = None,
    ) -> bool:
        """
        Initiates a sequential interactive review for a single action.

        Returns:
            True if the action should be executed, False if skipped.
        """
        ...
