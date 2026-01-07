from abc import ABC, abstractmethod
from teddy.core.domain.models import ExecutionReport


class RunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(self, plan_content: str) -> ExecutionReport:
        """
        Takes raw plan content, executes it, and returns a report.
        """
        pass
