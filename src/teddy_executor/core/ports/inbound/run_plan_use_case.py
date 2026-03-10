from abc import ABC, abstractmethod
from typing import Optional
from teddy_executor.core.domain.models import ExecutionReport, Plan


class IRunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
    ) -> ExecutionReport:
        """
        Executes a plan and returns a report.

        Args:
            plan: An already parsed Plan object.
            plan_content: Raw Markdown content of a plan.
            plan_path: Path to a plan file on disk.
            interactive: A flag to enable/disable step-by-step user approval.
        """
        pass

    @abstractmethod
    def resume(
        self, session_name: str, interactive: bool = True
    ) -> Optional[ExecutionReport]:
        """
        Intelligently resumes the session based on its state.

        Args:
            session_name: The name of the session to resume.
            interactive: Whether to run in interactive mode.
        """
        pass
