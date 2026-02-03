from abc import ABC, abstractmethod

from teddy_executor.core.domain.models import Plan


class InvalidPlanError(Exception):
    """Raised when the plan is malformed."""

    pass


class IPlanParser(ABC):
    """
    Defines the inbound port for parsing a plan from a raw string into a Plan object.
    This is the contract that all plan parser implementations must adhere to.
    """

    @abstractmethod
    def parse(self, plan_content: str) -> Plan:
        """
        Reads and parses the specified plan string into a structured Plan object.

        Args:
            plan_content: The raw string content of the plan.

        Returns:
            A Plan domain object.

        Raises:
            InvalidPlanError: If the plan content is malformed or invalid.
        """
        raise NotImplementedError
