from abc import ABC, abstractmethod
from teddy_executor.core.domain.models import ExecutionReport


class RunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(self, plan_content: str, interactive: bool) -> ExecutionReport:
        """
        Takes raw plan content, executes it, and returns a report.

        Args:
            plan_content: The YAML string representing the plan.
            interactive: A flag to enable/disable step-by-step user approval.
        """
        pass
