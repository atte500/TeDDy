from abc import ABC, abstractmethod

from teddy_executor.core.domain.models import Plan


from typing import Any, Optional, List


class InvalidPlanError(Exception):
    """Raised when the plan is malformed."""

    def __init__(
        self,
        message: str,
        offending_node: Optional[Any] = None,
        offending_nodes: Optional[List[Any]] = None,
        validation_errors: Optional[List[Any]] = None,
    ):
        super().__init__(message)
        self.offending_nodes = offending_nodes or []
        self.validation_errors = validation_errors or []
        if offending_node:
            self.offending_nodes.append(offending_node)

    @property
    def offending_node(self) -> Optional[Any]:
        """Backward compatibility for single offending node."""
        return self.offending_nodes[0] if self.offending_nodes else None


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
