from typing import Protocol, Optional, runtime_checkable
from teddy_executor.core.domain.models.plan import Plan


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
