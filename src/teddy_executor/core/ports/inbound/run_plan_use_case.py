from abc import ABC, abstractmethod
from teddy_executor.core.domain.models import ExecutionReport


from teddy_executor.core.domain.models import Plan


class RunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(self, plan: Plan, interactive: bool) -> ExecutionReport:
        """
        Takes a parsed Plan object, executes it, and returns a report.

        Args:
            plan: The parsed Plan object to execute.
            interactive: A flag to enable/disable step-by-step user approval.
        """
        pass
